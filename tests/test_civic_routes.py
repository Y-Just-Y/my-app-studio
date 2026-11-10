"""Isolated civic HTTP/security checks; all AI responses here are explicitly mocked."""

import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import httpx
import pytest

from app import civic_ai, civic_etl, civic_limits, civic_store, database, security
from app.main import create_app

REAL_MODEL_REQUEST = civic_ai._request
TEST_KEY = "unit-test-placeholder-not-a-real-openai-key"


@pytest.fixture(name="public_documents")
def fixture_public_documents():
    """Controlled examples use public-source fields, not the learner's runtime."""
    common = {
        "url": "https://newark.legistar.com/MeetingDetail.aspx?LEGID=302232&GID=7",
        "heading": "Meeting record",
        "fetched_at": "2026-11-10T18:00:00+00:00",
        "source_updated_at": "2026-10-30T18:00:00",
    }
    return [
        {
            **common,
            "source_id": "test-newark-meeting-november",
            "title": "Newark Municipal Council meeting — November 5, 2026",
            "text": "A Municipal Council meeting was scheduled for November 5, 2026 "
            "at 12:30 PM in the Council Chamber. This listing does not establish "
            "that the meeting occurred or that a measure passed.",
            "metadata": {"kind": "meeting", "meeting_date": "2026-11-05"},
        },
        {
            **common,
            "source_id": "test-newark-meeting-october",
            "title": "Newark Municipal Council meeting — October 21, 2026",
            "text": "The Municipal Council record lists October 21, 2026 at "
            "6:30 PM in the Council Chamber.",
            "metadata": {"kind": "meeting", "meeting_date": "2026-10-21"},
        },
        {
            **common,
            "source_id": "test-newark-agenda-housing",
            "title": "Controlled example: housing ordinance agenda item",
            "text": "The agenda includes a housing ordinance and a tax abatement. "
            "An agenda listing alone does not establish final passage.",
            "metadata": {"kind": "agenda_item", "meeting_date": "2026-11-05"},
        },
    ]


@pytest.fixture(name="civic_client")
def fixture_civic_client(settings, monkeypatch, public_documents):
    """Prevent inherited model configuration and reject accidental external calls."""
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "gpt-5-mini")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("CIVIC_AI_ENABLED", "0")

    def no_model_requests(*_args, **_kwargs):
        raise AssertionError(
            "An isolated source-search test attempted a model request."
        )

    monkeypatch.setattr(civic_ai, "_request", no_model_requests)
    application = create_app(settings)
    application.state.civic_allow_ai = False
    civic_store.upsert_documents(application.state.civic_database, public_documents)
    with TestClient(application, base_url=settings.origin) as browser:
        yield browser


def _csrf(client):
    return {"X-CSRF-Token": client.get("/api/csrf").json()["csrf_token"]}


def _question(client, question="Where was the council meeting?", mode="search"):
    return client.post(
        "/api/civic/chat",
        json={"question": question, "mode": mode},
        headers=_csrf(client),
    )


def _enable_mocked_ai(client, monkeypatch):
    """Enable only an in-process mocked provider; this cannot spend API credits."""
    client.app.state.civic_allow_ai = True
    monkeypatch.setenv("OPENAI_API_KEY", TEST_KEY)


def test_civic_catalog_excludes_accounts_and_provider_secrets(civic_client, settings):
    """Public counts come from the civic store, with no credentials/account records."""
    username = "private_civic_test_account"
    security.signup(settings, username, "a disposable test-only passphrase")
    response = civic_client.get("/api/civic/status")
    assert response.status_code == 200
    status = response.json()
    assert status["sources"] == status["chunks"] == 3
    assert status["provider"]["enabled"] is False
    assert status["provider"]["configured"] is False
    assert len(status["documents"]) == 3
    assert username not in response.text
    assert settings.secret not in response.text
    assert str(settings.database) not in response.text
    assert not {"password_hash", "csrf_token", "api_key"} & set(status)
    assert civic_client.app.state.civic_database != settings.database


def test_civic_page_escapes_source_titles_and_explains_ai_status(civic_client):
    """Source text stays inert HTML and the search-only state is visible."""
    database = civic_client.app.state.civic_database
    document = civic_store.snapshot(database)["documents"][0]
    document["title"] = '<script>alert("untrusted civic text")</script>'
    civic_store.upsert_documents(database, [document])
    response = civic_client.get("/ask")
    assert response.status_code == 200
    assert "AI generation is not connected yet" in response.text
    assert "&lt;script&gt;" in response.text
    assert '<script>alert("untrusted civic text")</script>' not in response.text
    assert 'src="/static/civic.js"' in response.text
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_keyword_http_returns_saved_source_evidence(civic_client):
    """Keyword search returns real imported chunks and original source URLs."""
    response = civic_client.get("/api/civic/search", params={"q": "housing ordinance"})
    assert response.status_code == 200
    result = response.json()
    assert result["mode"] == "keyword"
    assert result["sources"][0]["source_id"] == "test-newark-agenda-housing"
    assert "housing ordinance" in result["sources"][0]["text"]
    assert result["sources"][0]["url"].startswith("https://newark.legistar.com/")
    assert result["sources"][0]["chunk_id"].endswith("-v1-001")
    assert civic_client.get("/api/civic/search", params={"q": "hi"}).status_code == 422


def test_search_chat_is_honest_about_missing_evidence(civic_client):
    """A city name cannot supply an administrator password or a weather forecast."""
    response = _question(civic_client, "What is my Newark administrator password?")
    assert response.status_code == 200
    result = response.json()
    assert result["mode"] == "source_search"
    assert result["insufficient_evidence"] is True
    assert result["sources"] == []
    assert result["model"] is None
    assert "supporting information" in result["answer"]
    response = _question(civic_client, "Where was the council meeting?")
    assert response.status_code == 200
    assert response.json()["sources"]
    assert "not an AI-generated answer" in response.json()["answer"]


def test_chat_rejects_missing_or_wrong_csrf_before_spending(civic_client):
    """A direct cross-site chat POST does not initiate retrieval or model work."""
    body = {"question": "Where was the council meeting?", "mode": "search"}
    assert civic_client.post("/api/civic/chat", json=body).status_code == 403
    response = civic_client.post(
        "/api/civic/chat", json=body, headers={"X-CSRF-Token": "not-the-session-token"}
    )
    assert response.status_code == 403
    assert _question(civic_client).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "  "},
        {"question": "a" * 1001},
        {"question": "council meeting", "mode": "invented-mode"},
        {"question": "council meeting", "api_key": "must-not-be-accepted"},
        {"question": ["a", "b", "c"]},
    ],
)
def test_chat_rejects_invalid_or_client_selected_configuration(civic_client, payload):
    """Clients cannot choose credentials, models, retrieval URLs or excessive text."""
    response = civic_client.post(
        "/api/civic/chat", json=payload, headers=_csrf(civic_client)
    )
    assert response.status_code == 422
    assert "must-not-be-accepted" not in response.text


def test_chat_caps_raw_body_before_json_parsing(civic_client):
    """Byte limits apply to padding and streamed bodies as well as question length."""
    headers = {**_csrf(civic_client), "Content-Type": "application/json"}
    body = json.dumps({"question": "council meeting"}) + " " * 4096
    response = civic_client.post("/api/civic/chat", content=body, headers=headers)
    assert response.status_code == 413
    response = civic_client.post(
        "/api/civic/chat",
        content=iter([b'{"question":"', b"a" * 5000, b'"}']),
        headers=headers,
    )
    assert response.status_code == 413


def test_chat_rate_limit_ignores_spoofed_forwarded_addresses(civic_client):
    """The sixth request is rejected; caller-controlled forwarded IPs do not reset it."""
    headers = _csrf(civic_client)
    for index in range(5):
        response = civic_client.post(
            "/api/civic/chat",
            json={"question": "council meeting", "mode": "search"},
            headers={**headers, "X-Forwarded-For": f"192.0.2.{index}"},
        )
        assert response.status_code == 200
    response = civic_client.post(
        "/api/civic/chat",
        json={"question": "council meeting", "mode": "search"},
        headers={**headers, "X-Forwarded-For": "192.0.2.99"},
    )
    assert response.status_code == 429
    assert 1 <= int(response.headers["retry-after"]) <= 300


def test_application_ceiling_persists_in_separate_limit_store(civic_client):
    """A new client does not bypass the application-wide daily request ceiling."""
    database = civic_client.app.state.civic_database
    for index in range(30):
        civic_limits.consume(database, f"controlled-client-{index}")
    response = _question(civic_client)
    assert response.status_code == 429
    assert 1 <= int(response.headers["retry-after"]) <= 86400
    path = Path(database).with_name("civic-limits.sqlite3")
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT count FROM request_limits WHERE bucket='application'"
            ).fetchone()[0]
            == 30
        )


def test_unconfigured_ai_does_not_silently_fall_back_to_a_fake_answer(civic_client):
    """An explicit AI request reports the missing connection instead of claiming AI."""
    response = _question(civic_client, mode="ai")
    assert response.status_code == 503
    assert "not connected yet" in response.json()["detail"]


def test_mocked_ai_returns_only_cited_current_chunks(civic_client, monkeypatch):
    """This is a mocked gateway integration check, not a live AI-quality result."""
    _enable_mocked_ai(civic_client, monkeypatch)
    seen = {}

    def mocked_generation(question, chunks):
        seen["question"] = question
        seen["chunks"] = chunks
        return {
            "answer": "The saved meeting record lists the Council Chamber.",
            "citation_ids": [chunks[0]["chunk_id"]],
            "insufficient_evidence": False,
            "model": "mocked-test-provider",
        }

    monkeypatch.setattr(civic_ai, "generate_answer", mocked_generation)
    response = _question(civic_client, mode="ai")
    assert response.status_code == 200
    result = response.json()
    assert seen["question"] == "Where was the council meeting?"
    assert result["mode"] == "ai"
    assert result["model"] == "mocked-test-provider"
    assert len(result["sources"]) == 1
    assert result["sources"][0]["chunk_id"] == result["citation_ids"][0]
    assert TEST_KEY not in response.text


def test_ai_missing_evidence_never_calls_generation(civic_client, monkeypatch):
    """No-evidence handling is real even though AI configuration is simulated."""
    _enable_mocked_ai(civic_client, monkeypatch)

    def must_not_generate(*_args, **_kwargs):
        raise AssertionError("A no-evidence question must not initiate generation.")

    monkeypatch.setattr(civic_ai, "generate_answer", must_not_generate)
    response = _question(
        civic_client, "What is my Newark administrator password?", "ai"
    )
    assert response.status_code == 200
    assert response.json()["insufficient_evidence"] is True
    assert response.json()["sources"] == []
    assert response.json()["model"] is None


def test_upstream_error_body_and_key_never_reach_browser(civic_client, monkeypatch):
    """The actual gateway sanitizes a mocked upstream error before HTTP exposure."""
    _enable_mocked_ai(civic_client, monkeypatch)

    def rejected_request(_request):
        return httpx.Response(
            401, json={"error": "private upstream detail " + TEST_KEY}
        )

    transport = httpx.MockTransport(rejected_request)

    def mocked_transport_request(endpoint, payload, transport=None):
        del transport
        return REAL_MODEL_REQUEST(endpoint, payload, transport=mock_transport)

    mock_transport = transport
    monkeypatch.setattr(civic_ai, "_request", mocked_transport_request)
    response = _question(civic_client, mode="ai")
    assert response.status_code == 503
    assert TEST_KEY not in response.text
    assert "private upstream detail" not in response.text
    assert "did not accept" in response.json()["detail"]


def test_concurrent_ai_is_rejected_without_an_unbounded_queue(
    civic_client, monkeypatch
):
    """A held model slot makes another request retry explicitly instead of queuing."""
    _enable_mocked_ai(civic_client, monkeypatch)
    with civic_limits.one_request():
        response = _question(civic_client, mode="ai")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "10"


def _login_member(client, settings):
    """Use real signup validation, signed login cookies and session-bound CSRF."""
    username, password = "civic_route_member", "disposable civic-only test passphrase"
    security.signup(settings, username, password)
    response = client.post(
        "/api/login",
        json={"username": username, "password": password},
        headers=_csrf(client),
    )
    assert response.status_code == 200
    return username


def test_import_requires_current_admin_and_csrf(civic_client, settings, monkeypatch):
    """Anon/member requests cannot refresh; role changes apply to existing sessions."""
    called = []

    def mocked_import(path, as_of, limit):
        called.append((path, as_of, limit))
        return {"mocked_import": True, "load": {"unchanged": 3}}

    monkeypatch.setattr(civic_etl, "run_import", mocked_import)
    assert civic_client.post("/api/civic/import", json={"limit": 2}).status_code == 401
    username = _login_member(civic_client, settings)
    response = civic_client.post(
        "/api/civic/import", json={"limit": 2}, headers=_csrf(civic_client)
    )
    assert response.status_code == 403
    assert called == []
    database.set_role(settings, username, "admin")
    assert civic_client.post("/api/civic/import", json={"limit": 2}).status_code == 403
    response = civic_client.post(
        "/api/civic/import", json={"limit": 2}, headers=_csrf(civic_client)
    )
    assert response.status_code == 200
    assert response.json()["mocked_import"] is True
    assert len(called) == 1
    assert called[0][0] == civic_client.app.state.civic_database
    assert called[0][2] == 2
    database.set_role(settings, username, "member")
    response = civic_client.post(
        "/api/civic/import", json={"limit": 2}, headers=_csrf(civic_client)
    )
    assert response.status_code == 403
    assert len(called) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"limit": 0},
        {"limit": 6},
        {"limit": True},
        {"limit": "5"},
        {"limit": 2, "url": "https://untrusted.invalid/private"},
        {"limit": 2, "as_of": "2099-01-01"},
        {},
        [],
    ],
)
def test_admin_import_cannot_expand_scope_or_choose_urls(
    civic_client, settings, monkeypatch, payload
):
    """Even an admin cannot make this route a general-purpose authenticated fetcher."""
    username = _login_member(civic_client, settings)
    database.set_role(settings, username, "admin")

    def must_not_import(*_args, **_kwargs):
        raise AssertionError("Rejected import parameters must not reach the feed.")

    monkeypatch.setattr(civic_etl, "run_import", must_not_import)
    response = civic_client.post(
        "/api/civic/import", json=payload, headers=_csrf(civic_client)
    )
    assert response.status_code == 422
    assert "untrusted.invalid" not in response.text


def test_failed_admin_refresh_preserves_snapshot_and_hides_upstream_details(
    civic_client, settings, monkeypatch
):
    """A source outage is a safe 503, not disclosure or deletion of previous evidence."""
    username = _login_member(civic_client, settings)
    database.set_role(settings, username, "admin")
    before = civic_store.snapshot(civic_client.app.state.civic_database)

    def mocked_source_failure(*_args, **_kwargs):
        raise civic_etl.CivicImportError("private upstream detail " + TEST_KEY)

    monkeypatch.setattr(civic_etl, "run_import", mocked_source_failure)
    response = civic_client.post(
        "/api/civic/import", json={"limit": 5}, headers=_csrf(civic_client)
    )
    assert response.status_code == 503
    assert "Saved records were kept" in response.json()["detail"]
    assert TEST_KEY not in response.text
    assert "private upstream detail" not in response.text
    assert civic_store.snapshot(civic_client.app.state.civic_database) == before


def test_portfolio_lab_alias_reaches_public_chat(civic_client):
    """The route recorded in the earlier plan reaches the actual local chat page."""
    response = civic_client.get("/portfolio/lab", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/ask"
    response = civic_client.get("/portfolio/lab")
    assert response.status_code == 200
    assert "Ask Newark." in response.text
