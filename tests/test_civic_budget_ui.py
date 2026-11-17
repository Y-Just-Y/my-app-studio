"""Public budget presentation checks use controlled records, never API credit."""

from fastapi.testclient import TestClient

from app import civic_ai, civic_documents, civic_store
from app.main import create_app


def _budget_document():
    """Represent a controlled import with the reviewed source's declared fields."""
    return {
        "source_id": civic_documents.SUMMARY_SOURCE_ID,
        "title": "Newark 2026 introduced municipal budget",
        "url": civic_documents.PDF_URL + "#page=1",
        "heading": "2026 introduced budget summary in USD",
        "text": "Newark's INTRODUCED 2026 budget lists total general "
        "appropriations including reserve of $900,500,264.94 USD. "
        "This is not verified as an adopted budget.",
        "fetched_at": "2026-11-16T23:00:00+00:00",
        "metadata": {
            "kind": "budget",
            "status": "introduced",
            "year": 2026,
            "source_sha256": civic_documents.PDF_SHA256,
            "reviewed_at": "2026-11-16T22:00:00+00:00",
            "total_general_exclusive": "880149264.94",
            "reserve": "20351000.00",
            "total_general_including_reserve": "900500264.94",
            "municipal_taxation": "288267071.55",
            "raw_amounts": {},
            "coverage": "Selected summary and status pages; not the full budget.",
        },
    }


def test_budget_card_appears_only_after_a_reviewed_source_is_loaded(settings):
    """A working import fills its card while unrelated previews stay unfilled."""
    application = create_app(settings)
    with TestClient(application, base_url=settings.origin) as browser:
        assert "2026 · Introduced" not in browser.get("/").text
        civic_store.upsert_documents(
            application.state.civic_database, [_budget_document()]
        )
        response = browser.get("/")
        assert response.status_code == 200
        assert "2026 · Introduced" in response.text
        assert "$900,500,264.94" in response.text
        assert "$880,149,264.94" in response.text
        assert "$20,351,000.00" in response.text
        assert "$288,267,071.55" in response.text
        assert civic_documents.PDF_URL + "#page=1" in response.text
        assert "Adoption not verified" in response.text
        assert "Comparison city" in response.text
        assert "Not selected" in response.text


def test_budget_search_and_ai_page_keep_status_year_and_page(settings):
    """The new numbers reach retrieval with their proposal status attached."""
    application = create_app(settings)
    civic_store.upsert_documents(application.state.civic_database, [_budget_document()])
    with TestClient(application, base_url=settings.origin) as browser:
        result = browser.get(
            "/api/civic/search", params={"q": "2026 budget appropriations reserve"}
        ).json()
        passage = result["sources"][0]
        assert "INTRODUCED 2026" in passage["text"]
        assert passage["url"].endswith("#page=1")
        assert passage["metadata"]["status"] == "introduced"
        status = browser.get("/api/civic/status").json()
        assert status["budget"]["adoption_verified"] is False
        assert status["budget"]["display"]["reserve"] == "$20,351,000.00"
        ask = browser.get("/ask")
        assert ask.status_code == 200
        assert "Introduced 2026 budget" in ask.text
        assert "scanned budget changes need review" in ask.text


def test_approved_budget_request_stops_before_generation(settings, monkeypatch):
    """The HTTP path refuses an adoption claim without spending generation credit."""
    monkeypatch.setenv("OPENAI_API_KEY", "offline-budget-test-placeholder")
    application = create_app(settings)
    application.state.civic_allow_ai = True
    civic_store.upsert_documents(application.state.civic_database, [_budget_document()])

    def forbidden_model_call(*_args, **_kwargs):
        raise AssertionError("An unverified adoption claim reached the model.")

    monkeypatch.setattr(civic_ai, "_request", forbidden_model_call)
    with TestClient(application, base_url=settings.origin) as browser:
        token = browser.get("/api/csrf").json()["csrf_token"]
        response = browser.post(
            "/api/civic/chat",
            json={"question": "What is the approved 2026 budget?", "mode": "ai"},
            headers={"X-CSRF-Token": token},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["insufficient_evidence"] is True
        assert result["sources"] == []
        assert result["model"] is None
        assert result["status_guard"] == "budget_adoption"
        assert "$900" not in result["answer"]


def test_valid_citation_cannot_turn_proposal_into_approved_amount(
    settings, monkeypatch
):
    """A deliberately false mocked claim is replaced despite its valid citation."""
    monkeypatch.setenv("OPENAI_API_KEY", "offline-budget-test-placeholder")
    application = create_app(settings)
    application.state.civic_allow_ai = True
    civic_store.upsert_documents(application.state.civic_database, [_budget_document()])

    def false_approval(_question, chunks):
        return {
            "answer": "The approved 2026 budget is $900,500,264.94.",
            "citation_ids": [chunks[0]["chunk_id"]],
            "insufficient_evidence": False,
            "model": "offline-mock",
        }

    monkeypatch.setattr(civic_ai, "generate_answer", false_approval)
    with TestClient(application, base_url=settings.origin) as browser:
        token = browser.get("/api/csrf").json()["csrf_token"]
        result = browser.post(
            "/api/civic/chat",
            json={
                "question": "What does the introduced 2026 budget list?",
                "mode": "ai",
            },
            headers={"X-CSRF-Token": token},
        ).json()
        assert result["insufficient_evidence"] is True
        assert result["sources"] == []
        assert result["model"] == "offline-mock"
        assert "$900" not in result["answer"]
