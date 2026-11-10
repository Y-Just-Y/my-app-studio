"""Mocked provider contracts only; these do not establish live model access/quality."""

import json

import httpx
import pytest

from app import civic_ai


@pytest.fixture(autouse=True)
def isolated_ai_environment(monkeypatch):
    """No real key or provider request can be inherited from the host in this file."""
    for name in ("OPENAI_API_KEY", "OPENAI_CHAT_MODEL", "OPENAI_EMBEDDING_MODEL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def configured(monkeypatch):
    """A deliberately fake key is used only with an httpx.MockTransport."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-real-api-key")


@pytest.fixture
def chunks():
    """A synthetic meeting record, not a claim about a real Newark meeting."""
    return [
        {
            "chunk_id": "synthetic-meeting:v1:0",
            "title": "Synthetic council fixture",
            "heading": "Schedule",
            "text": "Synthetic example: Council meeting on November 5 at 12:30 PM.",
            "url": "https://example.invalid/fixture",
            "source_updated_at": "2026-10-30T18:47:56Z",
            "fetched_at": "2026-11-10T15:00:00Z",
        }
    ]


def model_response(answer=None, status="completed"):
    """Build the documented Responses wire shape without calling a model."""
    value = answer or {
        "answer": "The synthetic fixture lists November 5 at 12:30 PM.",
        "citation_ids": ["synthetic-meeting:v1:0"],
        "insufficient_evidence": False,
    }
    return {
        "status": status,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": json.dumps(value)}],
            }
        ],
    }


def test_missing_key_blocks_requests_without_exposing_key(chunks):
    """Neither generation nor embeddings may send an unconfigured request."""
    assert civic_ai.configuration_status() == {
        "configured": False,
        "chat_model": "gpt-5-mini",
        "embedding_model": "text-embedding-3-small",
    }
    with pytest.raises(civic_ai.ModelNotConfigured):
        civic_ai.generate_answer("When is the meeting?", chunks)
    with pytest.raises(civic_ai.ModelNotConfigured):
        civic_ai.embed_texts(["Public source text"])


def test_configured_status_never_returns_the_key(configured):
    """A browser-facing status includes model names only."""
    status = civic_ai.configuration_status()
    assert status["configured"] is True
    assert "test-only-not-a-real-api-key" not in json.dumps(status)


def test_generation_uses_fixed_endpoint_and_cited_structured_output(configured, chunks):
    """One mocked call checks privacy, schema and grounding instructions together."""
    calls = []

    def handle(request):
        calls.append(request)
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.headers["authorization"] == "Bearer test-only-not-a-real-api-key"
        payload = json.loads(request.content)
        assert payload["store"] is False
        assert payload["max_output_tokens"] == 1536
        assert payload["reasoning"]["effort"] == "low"
        assert "untrusted evidence" in payload["instructions"]
        assert "partial" in payload["instructions"]
        assert "America/New_York" in payload["instructions"]
        assert "missing record never establishes" in payload["instructions"]
        assert "retrieval timestamp" in payload["instructions"]
        schema = payload["text"]["format"]
        assert schema["type"] == "json_schema" and schema["strict"] is True
        assert schema["schema"]["properties"]["citation_ids"]["items"]["enum"] == [
            chunks[0]["chunk_id"]
        ]
        context = json.loads(payload["input"])
        assert context["question"] == "When is the meeting?"
        assert context["source_passages"][0]["text"] == chunks[0]["text"]
        return httpx.Response(200, json=model_response())

    result = civic_ai.generate_answer(
        "When is the meeting?", chunks, transport=httpx.MockTransport(handle)
    )
    assert result["citation_ids"] == [chunks[0]["chunk_id"]]
    assert result["model"] == "gpt-5-mini"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "value",
    [
        {"answer": "Unsupported", "citation_ids": [], "insufficient_evidence": False},
        {
            "answer": "Unsupported",
            "citation_ids": ["foreign"],
            "insufficient_evidence": False,
        },
        {"answer": "Unclear", "citation_ids": [], "insufficient_evidence": "false"},
        {"answer": "", "citation_ids": [], "insufficient_evidence": True},
        {
            "answer": "See https://invented.invalid",
            "citation_ids": [],
            "insufficient_evidence": True,
        },
        {
            "answer": "Unclear",
            "citation_ids": [],
            "insufficient_evidence": True,
            "extra": "bad",
        },
        {
            "answer": "Unclear",
            "citation_ids": ["synthetic-meeting:v1:0"],
            "insufficient_evidence": True,
        },
    ],
)
def test_unverifiable_model_answers_are_rejected(configured, chunks, value):
    """A JSON-shaped response alone does not establish usable source references."""
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json=model_response(value))
    )
    with pytest.raises(civic_ai.ModelServiceError):
        civic_ai.generate_answer("A question", chunks, transport=transport)


def test_model_can_report_insufficient_evidence(configured, chunks):
    """An honest unsupported-question result carries no fabricated citation."""
    value = {
        "answer": "The imported records do not establish that information.",
        "citation_ids": [],
        "insufficient_evidence": True,
    }
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json=model_response(value))
    )
    assert civic_ai.generate_answer("Unknown fact?", chunks, transport=transport)[
        "insufficient_evidence"
    ]


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_provider_errors_are_safe_and_never_retried(configured, chunks, status):
    """Errors cannot echo sensitive provider bodies and cannot duplicate spending."""
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            status,
            json={"error": "sensitive provider detail test-only-not-a-real-api-key"},
            headers={"location": "https://other.invalid"},
        )

    with pytest.raises(civic_ai.ModelServiceError) as error:
        civic_ai.generate_answer(
            "Question", chunks, transport=httpx.MockTransport(handle)
        )
    assert "sensitive provider detail" not in str(error.value)
    assert "test-only-not-a-real-api-key" not in str(error.value)
    assert len(calls) == 1


def test_network_errors_do_not_leak_request_headers(configured, chunks):
    """The upstream exception string is discarded."""

    def handle(request):
        raise httpx.ConnectError("test-only-not-a-real-api-key", request=request)

    with pytest.raises(civic_ai.ModelServiceError) as error:
        civic_ai.generate_answer(
            "Question", chunks, transport=httpx.MockTransport(handle)
        )
    assert "test-only" not in str(error.value)


def test_incomplete_generation_is_not_presented_as_an_answer(configured, chunks):
    """Exhausting output tokens cannot pass a partial answer to the interface."""
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json=model_response(status="incomplete"))
    )
    with pytest.raises(civic_ai.ModelServiceError, match="incomplete"):
        civic_ai.generate_answer("Question", chunks, transport=transport)


def test_large_provider_response_is_bounded(configured, chunks, monkeypatch):
    """A provider body limit is enforced before JSON parsing."""
    monkeypatch.setattr(civic_ai, "MAX_RESPONSE_BYTES", 32)
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=b"x" * 33)
    )
    with pytest.raises(civic_ai.ModelServiceError, match="size"):
        civic_ai.generate_answer("Question", chunks, transport=transport)


def test_embeddings_validate_indices_and_preserve_input_order(configured):
    """Out-of-order provider rows cannot attach vectors to the wrong text."""

    def handle(request):
        assert str(request.url) == "https://api.openai.com/v1/embeddings"
        payload = json.loads(request.content)
        assert payload == {
            "model": "text-embedding-3-small",
            "input": ["first", "second"],
            "encoding_format": "float",
        }
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.5, 0.25]},
                    {"index": 0, "embedding": [0.75, 0.5]},
                ]
            },
        )

    assert civic_ai.embed_texts(
        ["first", "second"], transport=httpx.MockTransport(handle)
    ) == [[0.75, 0.5], [0.5, 0.25]]


@pytest.mark.parametrize(
    "rows",
    [
        [{"index": 0, "embedding": [1.0]}, {"index": 0, "embedding": [1.0]}],
        [{"index": 0, "embedding": [1.0]}, {"index": 1, "embedding": [1.0, 2.0]}],
        [{"index": 0, "embedding": [0.0]}, {"index": 1, "embedding": [1.0]}],
        [{"index": 0, "embedding": [True]}, {"index": 1, "embedding": [1.0]}],
        [{"index": 0, "embedding": [float("nan")]}, {"index": 1, "embedding": [1.0]}],
        [{"index": 0, "embedding": [float("inf")]}, {"index": 1, "embedding": [1.0]}],
        [{"index": 0, "embedding": [1.0]}],
    ],
)
def test_invalid_embeddings_cannot_enter_the_index(configured, rows):
    """Nonfinite, duplicated, missing and dimension-mismatched vectors fail closed."""
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, text=json.dumps({"data": rows}))
    )
    with pytest.raises(civic_ai.ModelServiceError):
        civic_ai.embed_texts(["first", "second"], transport=transport)


def test_empty_or_oversized_inputs_are_rejected_before_http(configured, chunks):
    """Bound public input before invoking the paid provider."""
    for question in ("", " " * 2, "x" * 1001):
        with pytest.raises(ValueError):
            civic_ai.generate_answer(question, chunks)
    for texts in ([], [""], ["x"] * 33, ["x" * 8001]):
        with pytest.raises(ValueError):
            civic_ai.embed_texts(texts)
    with pytest.raises(ValueError):
        civic_ai.generate_answer("Question", [])
    with pytest.raises(ValueError):
        civic_ai.generate_answer("Question", chunks * 2)
