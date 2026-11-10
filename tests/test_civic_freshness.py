"""Version-race regressions with real isolated SQLite and mocked model calls only."""

from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from app import civic_ai, civic_store, civic_vectors
from app.main import create_app


@pytest.fixture(name="public_document")
def fixture_public_document():
    """A controlled public-shaped record is not a real-city factual claim."""
    return {
        "source_id": "freshness-test-meeting",
        "title": "Controlled Municipal Council meeting fixture",
        "url": "https://newark.legistar.com/MeetingDetail.aspx?LEGID=1&GID=7",
        "heading": "Meeting record",
        "text": "The controlled meeting fixture lists the Council Chamber as its "
        "location and November 5, 2026 as its scheduled date.",
        "metadata": {"kind": "meeting", "meeting_date": "2026-11-05"},
        "fetched_at": "2026-11-10T18:00:00+00:00",
        "source_updated_at": "2026-10-30T18:00:00",
    }


@pytest.fixture(name="freshness_client")
def fixture_freshness_client(settings, monkeypatch, public_document):
    """Explicit settings avoid dotenv; every real provider request is forbidden."""
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("CIVIC_AI_ENABLED", "0")
    monkeypatch.setattr(
        civic_ai,
        "configuration_status",
        lambda: {
            "configured": True,
            "chat_model": "mocked-freshness-provider",
            "embedding_model": "mocked-freshness-embedding",
        },
    )

    def no_provider_requests(*_args, **_kwargs):
        raise AssertionError("Freshness regressions must not make an API request.")

    monkeypatch.setattr(civic_ai, "_request", no_provider_requests)
    application = create_app(settings)
    application.state.civic_allow_ai = True
    civic_store.upsert_documents(application.state.civic_database, [public_document])
    with TestClient(application, base_url=settings.origin) as browser:
        yield browser


def _ask_ai(client):
    token = client.get("/api/csrf").json()["csrf_token"]
    return client.post(
        "/api/civic/chat",
        json={"question": "Where was the council meeting?", "mode": "ai"},
        headers={"X-CSRF-Token": token},
    )


def test_changed_source_during_generation_rejects_stale_answer_without_retry(
    freshness_client, public_document, monkeypatch
):
    """A completed model result cannot retain evidence replaced during that call."""
    database = freshness_client.app.state.civic_database
    old_id = civic_store.list_chunks(database)[0]["chunk_id"]
    calls = []

    def mocked_generation(question, chunks):
        calls.append((question, [row["chunk_id"] for row in chunks]))
        changed = deepcopy(public_document)
        changed["text"] = (
            "The corrected meeting fixture lists the Annex as its location."
        )
        civic_store.upsert_documents(database, [changed])
        return {
            "answer": "Stale fixture answer: the old Council Chamber location.",
            "citation_ids": [old_id],
            "insufficient_evidence": False,
            "model": "mocked-freshness-provider",
        }

    monkeypatch.setattr(civic_ai, "generate_answer", mocked_generation)
    response = _ask_ai(freshness_client)
    assert response.status_code == 409
    assert "source records changed" in response.json()["detail"]
    assert "Stale fixture answer" not in response.text
    assert old_id not in response.text
    assert len(calls) == 1
    assert civic_store.get_chunks(database, [old_id]) == []
    assert civic_store.list_chunks(database)[0]["version"] == 2


def test_changed_keyword_source_during_embedding_stops_before_generation(
    freshness_client, public_document, monkeypatch
):
    """The pre-embedding keyword snapshot must not enter fused answer context."""
    database = freshness_client.app.state.civic_database
    old_id = civic_store.list_chunks(database)[0]["chunk_id"]
    embedding_calls = []

    monkeypatch.setattr(
        civic_vectors,
        "index_status",
        lambda *_args: {"compatible": True, "indexed_chunks": 1},
    )

    def mocked_embedding(texts):
        embedding_calls.append(texts)
        changed = deepcopy(public_document)
        changed["text"] = "The meeting fixture was corrected to identify the Annex."
        civic_store.upsert_documents(database, [changed])
        return [[1.0, 0.0, 0.0]]

    def must_not_generate(*_args, **_kwargs):
        raise AssertionError("Generation must not use superseded keyword evidence.")

    def must_not_fuse(*_args, **_kwargs):
        raise AssertionError("Resolve stale keyword evidence before semantic fusion.")

    monkeypatch.setattr(civic_ai, "embed_texts", mocked_embedding)
    monkeypatch.setattr(civic_ai, "generate_answer", must_not_generate)
    monkeypatch.setattr(civic_vectors, "search_vectors", must_not_fuse)
    response = _ask_ai(freshness_client)
    assert response.status_code == 409
    assert "submit the question again" in response.json()["detail"]
    assert len(embedding_calls) == 1
    assert civic_store.get_chunks(database, [old_id]) == []


def test_unchanged_refetch_during_generation_preserves_answer_and_current_metadata(
    freshness_client, public_document, monkeypatch
):
    """A fresh fetch timestamp alone is not a changed evidence version."""
    database = freshness_client.app.state.civic_database
    old_id = civic_store.list_chunks(database)[0]["chunk_id"]
    calls = []
    new_fetch = "2026-11-10T18:05:00+00:00"

    def mocked_generation(question, chunks):
        calls.append((question, chunks))
        refreshed = deepcopy(public_document)
        refreshed["fetched_at"] = new_fetch
        refreshed["source_updated_at"] = "2026-11-10T18:04:00"
        refreshed["metadata"]["response_sha256"] = "changed-response-envelope-only"
        counts = civic_store.upsert_documents(database, [refreshed])
        assert counts["unchanged"] == 1
        return {
            "answer": "The controlled record lists the Council Chamber.",
            "citation_ids": [old_id],
            "insufficient_evidence": False,
            "model": "mocked-freshness-provider",
        }

    monkeypatch.setattr(civic_ai, "generate_answer", mocked_generation)
    response = _ask_ai(freshness_client)
    assert response.status_code == 200
    result = response.json()
    assert result["citation_ids"] == [old_id]
    assert result["sources"][0]["chunk_id"] == old_id
    assert result["sources"][0]["fetched_at"] == new_fetch
    assert result["sources"][0]["version"] == 1
    assert len(calls) == 1
