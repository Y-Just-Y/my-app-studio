"""Scheduled refresh contracts use synthetic documents and never provider calls."""

from datetime import date
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

import civic_refresh as refresh_cli
from app import civic_ai, civic_documents, civic_etl, civic_refresh, civic_store
from app import civic_vectors

DAY = date(2026, 11, 16)


def _document(identifier, text, kind="meeting"):
    return {
        "source_id": identifier,
        "title": "Synthetic " + identifier,
        "heading": "Synthetic public evidence",
        "text": text,
        "url": (
            civic_documents.PDF_URL + "#page=1"
            if kind == "budget"
            else "https://newark.legistar.com/MeetingDetail.aspx?ID=123"
        ),
        "fetched_at": "2026-11-16T20:00:00+00:00",
        "source_updated_at": None,
        "metadata": {"kind": kind, "status": "introduced", "year": 2026},
    }


@pytest.fixture(name="sources")
def synthetic_sources(monkeypatch):
    """Model access is forbidden even if the site's AI mode is configured."""
    meeting = _document("fixture-council", "Synthetic meeting at City Hall.")
    budget = _document(
        "newark-budget-2026-introduced-summary",
        "Synthetic INTRODUCED budget fixture, not an adopted total.",
        "budget",
    )
    monkeypatch.setattr(civic_etl, "fetch_documents", lambda *_a, **_k: [meeting])
    monkeypatch.setattr(civic_documents, "fetch_documents", lambda **_k: [budget])
    monkeypatch.setenv("OPENAI_API_KEY", "sk-synthetic-do-not-use")
    monkeypatch.setenv("CIVIC_AI_ENABLED", "1")
    monkeypatch.delenv("CIVIC_REFRESH_SCHEDULE", raising=False)

    def forbidden(*_args, **_kwargs):
        pytest.fail("A lexical refresh must never call an AI provider")

    monkeypatch.setattr(civic_ai, "embed_texts", forbidden)
    monkeypatch.setattr(civic_ai, "generate_answer", forbidden)
    return meeting, budget


def _rows(path):
    return civic_store.snapshot(path, limit=50)["documents"]


def test_status_reads_do_not_create_storage_or_claim_an_installed_timer(tmp_path):
    """A status read cannot initialize storage or invent timer installation."""
    path = tmp_path / "missing" / "civic.sqlite3"
    result = civic_refresh.refresh_status(path)
    assert result["status"] == "never_run"
    assert result["schedule"]["configured"] is False
    assert not path.parent.exists()


def test_refresh_is_idempotent_and_never_calls_models(tmp_path, sources):
    """Repeated source checks retain IDs and cannot spend provider credits."""
    path = tmp_path / "civic.sqlite3"
    first = civic_refresh.run_refresh(path, DAY)
    ids = [row["chunk_id"] for row in civic_store.list_chunks(path)]
    second = civic_refresh.run_refresh(path, DAY)
    assert first["status"] == second["status"] == "ok"
    assert first["load"]["inserted"] == second["load"]["unchanged"] == 2
    assert second["load"]["inserted"] == second["load"]["updated"] == 0
    assert ids == [row["chunk_id"] for row in civic_store.list_chunks(path)]
    assert second["semantic_index"]["requests"] == 0
    assert second["semantic_index"]["complete"] is False
    assert civic_refresh.refresh_status(path) == second
    assert sources[1]["source_id"] in {row["source_id"] for row in _rows(path)}


def test_budget_fetch_failure_keeps_verified_date_and_allows_council_update(
    tmp_path, sources, monkeypatch
):
    """A budget outage preserves old dates while a valid council update proceeds."""
    path = tmp_path / "civic.sqlite3"
    before = civic_refresh.run_refresh(path, DAY)
    budget_before = next(
        row for row in _rows(path) if row["metadata"]["kind"] == "budget"
    )
    sources[0]["text"] = "Synthetic updated meeting at another location."

    def failed(**_kwargs):
        raise civic_documents.DocumentFetchError("sk-secret /private/path HTTP body")

    monkeypatch.setattr(civic_documents, "fetch_documents", failed)
    result = civic_refresh.run_refresh(path, DAY)
    budget_after = next(
        row for row in _rows(path) if row["metadata"]["kind"] == "budget"
    )
    assert budget_after == budget_before
    assert result["status"] == "partial"
    assert result["load"]["updated"] == 1
    assert result["last_success_at"] == before["last_success_at"]
    assert (
        result["sources"]["budget_2026_introduced"]["last_success_at"]
        == before["sources"]["budget_2026_introduced"]["last_success_at"]
    )
    assert "sk-secret" not in json.dumps(result)
    assert "/private/path" not in json.dumps(result)


def test_changed_budget_scan_requires_review_without_replacing_facts(
    tmp_path, sources, monkeypatch
):
    """Unreviewed replacement bytes never replace verified budget passages."""
    path = tmp_path / "civic.sqlite3"
    civic_refresh.run_refresh(path, DAY)
    saved = _rows(path)

    def changed(**_kwargs):
        raise civic_documents.DocumentReviewRequired("Changed unreviewed bytes")

    monkeypatch.setattr(civic_documents, "fetch_documents", changed)
    result = civic_refresh.run_refresh(path, DAY)
    assert result["status"] == "review_required"
    assert result["sources"]["budget_2026_introduced"]["status"] == "review_required"
    assert _rows(path) == saved
    assert result["load"] == {"inserted": 0, "updated": 0, "unchanged": 1}
    assert sources[1]["text"] in {row["text"] for row in saved}


def test_all_fetch_failures_preserve_source_snapshot(tmp_path, sources, monkeypatch):
    """Source outages cannot empty or retimestamp the previously saved corpus."""
    path = tmp_path / "civic.sqlite3"
    civic_refresh.run_refresh(path, DAY)
    saved = _rows(path)

    def no_meetings(*_args, **_kwargs):
        raise civic_etl.CivicImportError("Untrusted source details")

    def no_budget(**_kwargs):
        raise civic_documents.DocumentFetchError("Untrusted PDF details")

    monkeypatch.setattr(civic_etl, "fetch_documents", no_meetings)
    monkeypatch.setattr(civic_documents, "fetch_documents", no_budget)
    result = civic_refresh.run_refresh(path, DAY)
    assert result["status"] == "error"
    assert _rows(path) == saved
    assert result["load"] == {"inserted": 0, "updated": 0, "unchanged": 0}
    assert sources[0]["source_id"] in {row["source_id"] for row in saved}


def test_invalid_batch_does_not_publish_partial_data_or_success_dates(
    tmp_path, sources
):
    """A rejected combined batch must not publish one successful-looking source."""
    path = tmp_path / "civic.sqlite3"
    previous = civic_refresh.run_refresh(path, DAY)
    saved = _rows(path)
    sources[0]["text"] = "Changed council text must also roll back."
    sources[1]["title"] = ""
    result = civic_refresh.run_refresh(path, DAY)
    assert result["status"] == "error"
    assert result["last_success_at"] == previous["last_success_at"]
    assert _rows(path) == saved
    assert all(source["status"] == "error" for source in result["sources"].values())


def test_admin_and_scheduled_import_share_the_same_lock(tmp_path, sources):
    """An active scheduled writer excludes manual/admin imports and other jobs."""
    path = tmp_path / "civic.sqlite3"
    civic_refresh.run_refresh(path, DAY)
    receipt = path.with_name("civic-refresh-status.json").read_bytes()
    with civic_refresh.writer_lock(path):
        with pytest.raises(civic_etl.CivicImportError, match="Another civic import"):
            civic_etl.run_import(path, DAY)
        assert civic_refresh.run_refresh(path, DAY)["status"] == "busy"
        assert path.with_name("civic-refresh-status.json").read_bytes() == receipt
    assert sources[0]["source_id"] in {row["source_id"] for row in _rows(path)}


def test_writer_lock_excludes_an_independent_process_and_releases_after_error(tmp_path):
    """The writer guard works across processes and releases on Python exceptions."""
    path = tmp_path / "civic.sqlite3"
    code = (
        "import sys; from app.civic_refresh import writer_lock, RefreshBusy; "
        "\ntry:\n with writer_lock(sys.argv[1]): print('acquired')"
        "\nexcept RefreshBusy: print('busy')"
    )
    with civic_refresh.writer_lock(path):
        child = subprocess.run(
            [sys.executable, "-c", code, str(path)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        assert child.stdout.strip() == "busy"
    with pytest.raises(RuntimeError, match="synthetic failure"):
        with civic_refresh.writer_lock(path):
            raise RuntimeError("synthetic failure")
    with civic_refresh.writer_lock(path):
        assert path.with_name("civic-refresh.lock").is_file()


def test_status_allowlist_hides_paths_keys_and_untrusted_fields(tmp_path, monkeypatch):
    """The public receipt must not reflect exception text or arbitrary source URLs."""
    path = tmp_path / "civic.sqlite3"
    raw = {
        "schema_version": 1,
        "status": "partial",
        "message": "sk-secret /private/runtime traceback",
        "database": "/private/runtime/civic.sqlite3",
        "sources": {"council": {"status": "error", "url": "https://evil.invalid"}},
        "semantic_index": {"requests": "sk-secret"},
    }
    path.with_name("civic-refresh-status.json").write_text(json.dumps(raw))
    monkeypatch.setenv("CIVIC_REFRESH_SCHEDULE", "nightly")
    result = civic_refresh.refresh_status(path)
    assert result["schedule"]["configured"] is True
    serialized = json.dumps(result)
    assert all(
        value not in serialized
        for value in ["sk-secret", "/private", "evil.invalid", "traceback"]
    )
    assert result["sources"]["council"]["url"] == civic_refresh.SOURCE_URLS["council"]
    assert result["semantic_index"]["requests"] == 0
    raw["sources"] = "not a dictionary"
    path.with_name("civic-refresh-status.json").write_text(json.dumps(raw))
    assert civic_refresh.refresh_status(path)["status"] == "unavailable"


def test_account_and_limit_files_are_not_modified(tmp_path, sources):
    """The lexical job must leave unrelated private databases byte-for-byte intact."""
    for name in ("studio.sqlite3", "civic-limits.sqlite3"):
        with sqlite3.connect(tmp_path / name) as connection:
            connection.execute("CREATE TABLE protected_fixture(value TEXT)")
            connection.execute("INSERT INTO protected_fixture VALUES ('preserve me')")
    before = {
        name: (tmp_path / name).read_bytes()
        for name in ("studio.sqlite3", "civic-limits.sqlite3")
    }
    civic_refresh.run_refresh(tmp_path / "civic.sqlite3", DAY)
    assert all((tmp_path / name).read_bytes() == data for name, data in before.items())
    assert sources[0]["source_id"] in {
        row["source_id"] for row in _rows(tmp_path / "civic.sqlite3")
    }


def test_changed_text_reports_a_lagging_semantic_index(tmp_path, sources):
    """A lexical-only source change cannot claim a complete semantic index."""
    path = tmp_path / "civic.sqlite3"
    civic_refresh.run_refresh(path, DAY)
    # Numeric vectors prove index readiness mechanics only, never semantic quality.
    civic_vectors.index_chunks(
        path, lambda texts: [[1.0, 0.0] for _ in texts], "fixture", dimensions=2
    )
    sources[0]["text"] = "Synthetic changed meeting evidence."
    result = civic_refresh.run_refresh(path, DAY)
    assert result["semantic_index"]["indexed_chunks"] == 1
    assert result["semantic_index"]["total_chunks"] == 2
    assert result["semantic_index"]["complete"] is False
    assert result["semantic_index"]["requests"] == 0


def test_cli_rejects_arbitrary_sources_before_refresh(monkeypatch):
    """The job cannot expand its fixed official-source manifest from CLI input."""

    def forbidden(*_args, **_kwargs):
        pytest.fail("Invalid CLI scope must not run a refresh")

    monkeypatch.setattr(refresh_cli, "run_refresh", forbidden)
    with pytest.raises(SystemExit) as stopped:
        refresh_cli.main(["--url", "https://untrusted.invalid"])
    assert stopped.value.code == 2


def test_database_error_updates_receipt_without_exposing_exception(
    tmp_path, sources, monkeypatch
):
    """SQLite operational failures replace a stale success with a safe error."""
    path = tmp_path / "civic.sqlite3"
    previous = civic_refresh.run_refresh(path, DAY)
    saved = _rows(path)

    def database_busy(*_args, **_kwargs):
        raise sqlite3.OperationalError("sk-secret /private/database locked")

    monkeypatch.setattr(civic_store, "upsert_documents", database_busy)
    result = civic_refresh.run_refresh(path, DAY)
    assert result["status"] == civic_refresh.refresh_status(path)["status"] == "error"
    assert result["last_success_at"] == previous["last_success_at"]
    assert "sk-secret" not in json.dumps(result)
    assert _rows(path) == saved
    assert sources[1]["source_id"] in {row["source_id"] for row in saved}


def test_cli_reports_partial_failure_as_unsuccessful(monkeypatch, capsys):
    """The timer can observe an incomplete refresh without an automatic retry."""
    monkeypatch.setattr(
        refresh_cli, "run_refresh", lambda *_args, **_kwargs: {"status": "partial"}
    )
    assert refresh_cli.main([]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "partial"
