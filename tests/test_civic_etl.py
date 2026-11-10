"""Isolated civic import/retrieval checks; fixture titles are controlled examples."""

from datetime import date
import json
from pathlib import Path
import sqlite3

import httpx
import pytest

from app import civic_etl, civic_store

FIXTURES = Path(__file__).parent / "fixtures" / "civic"


def source_client(
    *, status=200, events=None, agenda=None, page_status=200, fallback_record=None
):
    """Serve controlled official-schema payloads without using the network."""
    events = (
        events
        if events is not None
        else json.loads((FIXTURES / "meetings.json").read_text())
    )
    agenda = (
        agenda
        if agenda is not None
        else json.loads((FIXTURES / "agenda.json").read_text())
    )

    def respond(request):
        assert "token" not in request.url.params
        if request.url.host == "newark.legistar.com":
            return httpx.Response(page_status, content=b"Official meeting page fixture")
        assert request.url.host == "webapi.legistar.com"
        pieces = request.url.path.strip("/").split("/")
        if len(pieces) == 4 and pieces[2] == "events":
            record = fallback_record if fallback_record is not None else events[0]
            return httpx.Response(status, json=record)
        if len(pieces) == 4 and pieces[2] == "eventitems":
            selected = next(
                row for row in agenda if row["EventItemId"] == int(pieces[-1])
            )
            record = {**selected, "EventItemEventId": events[0]["EventId"]}
            return httpx.Response(status, json=record)
        if request.url.path.endswith("eventitems"):
            assert request.url.params["$top"] == "100"
            return httpx.Response(status, json=agenda)
        assert request.url.params["$top"] == "5"
        assert "Municipal Council" in request.url.params["$filter"]
        return httpx.Response(status, json=events)

    return httpx.Client(transport=httpx.MockTransport(respond))


def test_import_preserves_provenance_and_local_meeting_time(tmp_path):
    """Dates stay local; agenda-final is not mistaken for an event outcome."""
    path = tmp_path / "civic.sqlite3"
    with source_client() as client:
        report = civic_etl.run_import(path, date(2026, 11, 10), client=client)
    assert report["extract"] == {"meetings": 1, "agenda_items": 1}
    assert report["load"] == {"inserted": 2, "updated": 0, "unchanged": 0}
    assert report["chunks"] == 2
    meeting = next(
        d
        for d in civic_store.snapshot(path)["documents"]
        if d["metadata"]["kind"] == "meeting"
    )
    assert meeting["metadata"]["meeting_date"] == "2026-11-05"
    assert meeting["metadata"]["meeting_starts_at"] == "2026-11-05T12:30:00-05:00"
    assert meeting["metadata"]["timezone"] == "America/New_York"
    assert meeting["url"].startswith("https://newark.legistar.com/MeetingDetail.aspx")
    assert meeting["metadata"]["original_page_url"] == meeting["url"]
    assert meeting["metadata"]["original_http_status"] == 200
    assert meeting["metadata"]["link_checked_at"] == meeting["fetched_at"]
    assert len(meeting["content_hash"]) == 64
    assert "does not establish" in meeting["text"]


def test_reimport_has_stable_chunks_and_versions(tmp_path):
    """Delivering the same source twice does not duplicate searchable evidence."""
    path = tmp_path / "civic.sqlite3"
    with source_client() as client:
        first = civic_etl.run_import(path, date(2026, 11, 10), client=client)
        identifiers = [row["chunk_id"] for row in civic_store.list_chunks(path)]
        second = civic_etl.run_import(path, date(2026, 11, 10), client=client)
    assert first["sources"] == second["sources"] == 2
    assert second["load"] == {"inserted": 0, "updated": 0, "unchanged": 2}
    assert identifiers == [row["chunk_id"] for row in civic_store.list_chunks(path)]


def test_changed_source_replaces_only_its_own_chunks(tmp_path):
    """Old evidence vanishes while the unrelated meeting source remains intact."""
    path = tmp_path / "civic.sqlite3"
    with source_client() as client:
        documents = civic_etl.fetch_documents(date(2026, 11, 10), client=client)
    civic_store.upsert_documents(path, documents)
    old = civic_store.search(path, "abatement")[0]
    preserved_id = next(
        row["chunk_id"]
        for row in civic_store.list_chunks(path)
        if row["metadata"]["kind"] == "meeting"
    )
    agenda = documents[1]
    agenda["title"] = "Replacement public park grant"
    agenda["text"] = "A controlled updated source about public park grants."
    counts = civic_store.upsert_documents(path, [agenda])
    assert counts["updated"] == 1
    assert civic_store.search(path, "abatement") == []
    assert civic_store.get_chunks(path, [old["chunk_id"]]) == []
    assert civic_store.get_chunks(path, [preserved_id])[0]["chunk_id"] == preserved_id
    assert civic_store.search(path, "park grants")[0]["version"] == 2


def test_retrieval_does_not_match_unrelated_question_on_city_name(tmp_path):
    """A shared city word does not supply evidence for a secret or unrelated claim."""
    path = tmp_path / "civic.sqlite3"
    with source_client() as client:
        civic_etl.run_import(path, date(2026, 11, 10), client=client)
    assert civic_store.search(path, "What is my Newark administrator password?") == []
    assert civic_store.search(path, "What is Newark's hurricane forecast?") == []
    assert civic_store.search(path, "When was the council meeting?")
    assert civic_store.search(path, 'budget" OR 1=1 --') == []


def test_failed_extract_preserves_last_successful_snapshot(tmp_path):
    """A network failure never replaces the database with partial or empty output."""
    path = tmp_path / "civic.sqlite3"
    with source_client() as client:
        civic_etl.run_import(path, date(2026, 11, 10), client=client)
    before = civic_store.snapshot(path)
    with source_client(status=503) as client:
        with pytest.raises(
            civic_etl.CivicImportError, match="Existing records were kept"
        ):
            civic_etl.run_import(path, date(2026, 11, 10), client=client)
    assert civic_store.snapshot(path) == before


def test_future_or_redirected_source_is_rejected_before_load(tmp_path):
    """The recent-record snapshot cannot silently change scope or follow redirects."""
    path = tmp_path / "civic.sqlite3"
    events = json.loads((FIXTURES / "meetings.json").read_text())
    events[0]["EventDate"] = "2027-01-01T00:00:00"
    with source_client(events=events) as client:
        with pytest.raises(civic_etl.CivicImportError, match="future meeting"):
            civic_etl.run_import(path, date(2026, 11, 10), client=client)
    assert not path.exists()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(302, headers={"Location": "https://other.invalid"})
        )
    ) as client:
        with pytest.raises(civic_etl.CivicImportError):
            civic_etl.run_import(path, date(2026, 11, 10), client=client)
    assert not path.exists()


def test_chunk_boundaries_and_bulk_validation(tmp_path):
    """Large records stay bounded, and invalid batches cannot partly commit."""
    path = tmp_path / "civic.sqlite3"
    with source_client() as client:
        documents = civic_etl.fetch_documents(date(2026, 11, 10), client=client)
    documents[0]["text"] = "\n\n".join(["A complete paragraph. " * 65] * 3)
    civic_store.upsert_documents(path, documents)
    rows = civic_store.list_chunks(path)
    assert all(len(row["text"]) <= civic_store.MAX_CHUNK_CHARACTERS for row in rows)
    assert len(rows) > len(documents)
    before = civic_store.snapshot(path)
    documents[0]["text"] = "A new source version that must not be committed."
    documents[1]["url"] = "https://other.invalid/source"
    with pytest.raises(ValueError, match="official publishers"):
        civic_store.upsert_documents(path, documents)
    assert civic_store.snapshot(path) == before


def test_unrelated_fetch_changes_do_not_reversion_a_source(tmp_path):
    """A page-level API hash changing elsewhere is not a source content change."""
    path = tmp_path / "civic.sqlite3"
    with source_client() as client:
        documents = civic_etl.fetch_documents(date(2026, 11, 10), client=client)
    civic_store.upsert_documents(path, documents)
    chunk_ids = [row["chunk_id"] for row in civic_store.list_chunks(path)]
    documents[0]["metadata"]["response_sha256"] = "a changed response-page hash"
    documents[0]["metadata"]["api_url"] += "&another-read=1"
    documents[0]["metadata"]["link_checked_at"] = "2026-11-10T19:00:00+00:00"
    counts = civic_store.upsert_documents(path, documents)
    assert counts["unchanged"] == 2
    assert chunk_ids == [row["chunk_id"] for row in civic_store.list_chunks(path)]


def test_civic_database_does_not_create_account_tables(tmp_path):
    """Public retrieval evidence is isolated from authentication/session storage."""
    path = tmp_path / "civic.sqlite3"
    civic_store.initialize(path)
    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "civic_sources" in tables
    assert not {"users", "sessions", "login_attempts"} & tables


@pytest.mark.parametrize("page_status", [404, 410])
def test_missing_original_page_uses_only_verified_same_record_api(
    tmp_path, page_status
):
    """A dead page keeps its provenance while a matching official record is linked."""
    path = tmp_path / "civic.sqlite3"
    with source_client(page_status=page_status) as client:
        civic_etl.run_import(path, date(2026, 11, 10), client=client)
    documents = civic_store.snapshot(path)["documents"]
    meeting = next(d for d in documents if d["metadata"]["kind"] == "meeting")
    assert meeting["url"] == "https://webapi.legistar.com/v1/newark/events/302232"
    assert meeting["metadata"]["original_page_url"].startswith(
        "https://newark.legistar.com/MeetingDetail.aspx"
    )
    assert meeting["metadata"]["original_http_status"] == page_status
    assert meeting["metadata"]["link_resolution"] == "verified_official_api_record"
    assert meeting["metadata"]["link_checked_at"] == meeting["fetched_at"]
    agenda = next(d for d in documents if d["metadata"]["kind"] == "agenda_item")
    assert agenda["url"] == "https://webapi.legistar.com/v1/newark/eventitems/517475"


def test_wrong_record_api_never_replaces_a_dead_page_link(tmp_path):
    """A successful HTTP response is insufficient if it names a different record."""
    path = tmp_path / "civic.sqlite3"
    record = json.loads((FIXTURES / "meetings.json").read_text())[0]
    record["EventId"] += 1
    with source_client(page_status=410, fallback_record=record) as client:
        with pytest.raises(civic_etl.CivicImportError, match="did not match"):
            civic_etl.run_import(path, date(2026, 11, 10), client=client)
    assert not path.exists()


@pytest.mark.parametrize("page_status", [302, 403, 429, 503])
def test_transient_or_redirected_pages_do_not_authorize_api_fallback(
    tmp_path, page_status
):
    """Only 404/410 can change the citation target; outages keep the saved snapshot."""
    path = tmp_path / "civic.sqlite3"
    with source_client() as client:
        civic_etl.run_import(path, date(2026, 11, 10), client=client)
    before = civic_store.snapshot(path)
    with source_client(page_status=page_status) as client:
        with pytest.raises(
            civic_etl.CivicImportError, match="source page is unavailable"
        ):
            civic_etl.run_import(path, date(2026, 11, 10), client=client)
    assert civic_store.snapshot(path) == before


def test_same_api_host_cannot_expand_source_links_to_other_cities(tmp_path):
    """The added API publisher permits only one identified Newark event/item."""
    with source_client() as client:
        documents = civic_etl.fetch_documents(date(2026, 11, 10), client=client)
    documents[0]["url"] = "https://webapi.legistar.com/v1/another-city/events/302232"
    with pytest.raises(ValueError, match="one official Newark record"):
        civic_store.upsert_documents(tmp_path / "civic.sqlite3", documents)
