"""Bounded lexical refreshes of selected official sources, with no model calls."""

from contextlib import contextmanager
from datetime import date, datetime, timezone
import errno
import importlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from zoneinfo import ZoneInfo

from app import civic_store, civic_vectors
from app.private_files import private_directory, private_file

SOURCE_URLS = {
    "council": "https://webapi.legistar.com/v1/newark",
    "budget_2026_introduced": (
        "https://www.newarknj.gov/DocumentCenter/View/3062/"
        "2026-City-of-Newark-Introduced--Legal-Line-Budget-"
    ),
}
MESSAGES = {
    "never_run": "No automated refresh has been recorded yet.",
    "ok": "The selected official sources were checked. Source search is current.",
    "partial": "Some sources could not be checked. Their saved records were kept.",
    "review_required": (
        "A changed budget document needs review. Verified budget records were kept."
    ),
    "error": (
        "The refresh could not finish. Inspect the saved source status before retrying."
    ),
    "busy": "Another civic import is already running. This attempt was skipped.",
    "unavailable": "Refresh status is temporarily unavailable.",
}
MAX_STATUS_BYTES = 32_768


class RefreshBusy(RuntimeError):
    """A separate process already holds the civic writer lock."""


def _lock_operation(descriptor, acquire):
    if os.name == "nt":
        module = importlib.import_module("msvcrt")
        os.lseek(descriptor, 0, os.SEEK_SET)
        module.locking(descriptor, module.LK_NBLCK if acquire else module.LK_UNLCK, 1)
    else:
        module = importlib.import_module("fcntl")
        operation = module.LOCK_EX | module.LOCK_NB if acquire else module.LOCK_UN
        module.flock(descriptor, operation)


@contextmanager
def writer_lock(database):
    """Coordinate CLI/admin writers; the OS releases the lock after a crash.

    Keep the ordinary lock file after closing it. Unlinking it could let two
    callers lock different inodes and both believe they own the same resource.
    """
    path = Path(database).with_name("civic-refresh.lock")
    private_directory(path.parent)
    if path.is_symlink():
        raise ValueError("The civic refresh lock must be an ordinary file.")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    locked = False
    try:
        private_file(path)
        try:
            _lock_operation(descriptor, True)
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise RefreshBusy(MESSAGES["busy"]) from None
            raise
        locked = True
        yield
    finally:
        try:
            if locked:
                _lock_operation(descriptor, False)
        finally:
            os.close(descriptor)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _blank(status):
    return {
        "schema_version": 1,
        "status": status,
        "message": MESSAGES[status],
        "started_at": None,
        "completed_at": None,
        "last_success_at": None,
        "sources": {
            key: {
                "url": url,
                "status": "not_run",
                "last_success_at": None,
                "documents": 0,
            }
            for key, url in SOURCE_URLS.items()
        },
        "load": {"inserted": 0, "updated": 0, "unchanged": 0},
        "corpus": {"sources": 0, "chunks": 0},
        "semantic_index": {
            "indexed_chunks": 0,
            "total_chunks": 0,
            "complete": False,
            "mode": "manual",
            "requests": 0,
        },
        "schedule": {
            "configured": os.getenv("CIVIC_REFRESH_SCHEDULE", "disabled") == "nightly",
            "time": "03:15",
            "timezone": "America/New_York",
        },
    }


def _number(value):
    return (
        value
        if isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= 1_000_000
        else 0
    )


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 80:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(timezone.utc).isoformat() if parsed.tzinfo else None
    except ValueError:
        return None


def _public_report(raw):
    """Allowlist every browser field; never expose exception text or runtime paths."""
    if (
        not isinstance(raw, dict)
        or raw.get("schema_version") != 1
        or raw.get("status") not in MESSAGES
    ):
        return _blank("unavailable")
    result = _blank(raw["status"])
    for key in ("started_at", "completed_at", "last_success_at"):
        result[key] = _timestamp(raw.get(key))
    for key in SOURCE_URLS:
        source = raw.get("sources", {}).get(key, {})
        if not isinstance(source, dict):
            continue
        state = source.get("status")
        if state in {"not_run", "ok", "error", "review_required"}:
            result["sources"][key]["status"] = state
        result["sources"][key]["last_success_at"] = _timestamp(
            source.get("last_success_at")
        )
        result["sources"][key]["documents"] = _number(source.get("documents"))
    for group in ("load", "corpus"):
        values = raw.get(group, {})
        if isinstance(values, dict):
            for key in result[group]:
                result[group][key] = _number(values.get(key))
    index = raw.get("semantic_index", {})
    if isinstance(index, dict):
        for key in ("indexed_chunks", "total_chunks"):
            result["semantic_index"][key] = _number(index.get(key))
        result["semantic_index"]["complete"] = (
            index.get("complete") is True
            and 0
            < result["semantic_index"]["total_chunks"]
            == result["semantic_index"]["indexed_chunks"]
        )
    return result


def refresh_status(database):
    """Read a sanitized receipt without creating files, calling sources or models."""
    path = Path(database).with_name("civic-refresh-status.json")
    if not path.exists():
        return _blank("never_run")
    try:
        if path.is_symlink() or path.stat().st_size > MAX_STATUS_BYTES:
            return _blank("unavailable")
        return _public_report(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, AttributeError):
        return _blank("unavailable")


def _save_report(database, report):
    path = Path(database).with_name("civic-refresh-status.json")
    if path.is_symlink():
        raise ValueError("Refresh status must be an ordinary file.")
    descriptor, name = tempfile.mkstemp(prefix=".civic-refresh-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            private_file(temporary)
            json.dump(_public_report(report), stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _fetch_sources(as_of, limit, meeting_client, budget_client, report):
    etl = importlib.import_module("app.civic_etl")
    documents = importlib.import_module("app.civic_documents")
    collected = []
    for key, fetch in (
        ("council", lambda: etl.fetch_documents(as_of, limit, client=meeting_client)),
        (
            "budget_2026_introduced",
            lambda: documents.fetch_documents(client=budget_client),
        ),
    ):
        try:
            batch = fetch()
            collected.extend(batch)
            report["sources"][key].update(status="ok", documents=len(batch))
        except documents.DocumentReviewRequired:
            report["sources"][key]["status"] = "review_required"
        except (
            etl.CivicImportError,
            documents.DocumentFetchError,
            OSError,
            ValueError,
        ):
            report["sources"][key]["status"] = "error"
    return collected


def _run_locked(database, as_of, limit, meeting_client, budget_client):
    previous = refresh_status(database)
    report = _blank("ok")
    report["started_at"] = _now()
    report["last_success_at"] = previous["last_success_at"]
    for key in SOURCE_URLS:
        for field in ("last_success_at", "documents"):
            report["sources"][key][field] = previous["sources"][key][field]
    documents = _fetch_sources(as_of, limit, meeting_client, budget_client, report)
    try:
        if documents:
            report["load"] = civic_store.upsert_documents(database, documents)
        completed = _now()
        for source in report["sources"].values():
            if source["status"] == "ok":
                source["last_success_at"] = completed
        states = {source["status"] for source in report["sources"].values()}
        if "review_required" in states:
            report["status"] = "review_required"
        elif "error" in states:
            report["status"] = "partial" if "ok" in states else "error"
        if report["status"] == "ok":
            report["last_success_at"] = completed
    except (ValueError, OSError, sqlite3.Error):
        report["status"] = "error"
        for key in SOURCE_URLS:
            if report["sources"][key]["status"] == "ok":
                report["sources"][key]["status"] = "error"
                report["sources"][key]["documents"] = previous["sources"][key][
                    "documents"
                ]
            report["sources"][key]["last_success_at"] = previous["sources"][key][
                "last_success_at"
            ]
    try:
        snapshot = civic_store.snapshot(database)
        report["corpus"] = {key: snapshot[key] for key in ("sources", "chunks")}
        index = civic_vectors.index_status(database)
        report["semantic_index"].update(
            {key: index[key] for key in ("indexed_chunks", "total_chunks", "complete")}
        )
    except (ValueError, OSError, sqlite3.Error):
        report["status"] = "error"
        report["corpus"] = previous["corpus"]
        report["semantic_index"] = previous["semantic_index"]
    report["completed_at"] = _now()
    _save_report(database, report)
    return _public_report(report)


def run_refresh(
    database, as_of=None, *, limit=5, meeting_client=None, budget_client=None
):
    """Refresh fixed sources once; changed scans and embeddings need separate review."""
    as_of = as_of or datetime.now(ZoneInfo("America/New_York")).date()
    if (
        not isinstance(as_of, date)
        or not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= 5
    ):
        raise ValueError("Choose a date and between one and five council records.")
    try:
        with writer_lock(database):
            return _run_locked(database, as_of, limit, meeting_client, budget_client)
    except RefreshBusy:
        return _blank("busy")
