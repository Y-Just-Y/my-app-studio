"""Read-only public civic retrieval and an explicitly configured AI gateway."""

from datetime import datetime
import hashlib
import json
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from app import civic_ai, civic_etl, civic_limits, civic_store, civic_vectors, security
from app.features.accounts import api_csrf

router = APIRouter()


class Question(BaseModel):
    """A question never chooses an upstream URL, model, credentials or SQL."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=3, max_length=1000)
    mode: str = Field(default="search", pattern=r"^(search|ai)$")


def status(request):
    """Only public counts and configuration flags may reach the browser."""
    database = request.app.state.civic_database
    source_status = civic_store.snapshot(database, limit=5)
    provider = civic_ai.configuration_status()
    provider["enabled"] = request.app.state.civic_allow_ai and provider["configured"]
    return {
        **source_status,
        "provider": provider,
        "vectors": civic_vectors.index_status(database, provider["embedding_model"]),
        "coverage": (
            "A bounded snapshot of recent council records, not a complete calendar."
        ),
    }


@router.get("/ask", include_in_schema=False)
def ask_page(request: Request):
    """Make evidence and the current AI connection state visible before asking."""
    return request.app.state.templates.TemplateResponse(
        request=request, name="civic_chat.html", context={"civic": status(request)}
    )


@router.get("/research", include_in_schema=False)
def research_page(request: Request):
    """Publish the project methods, primary research and measured limits."""
    return request.app.state.templates.TemplateResponse(
        request=request, name="civic_research.html", context={"civic": status(request)}
    )


@router.get("/portfolio/lab", include_in_schema=False)
def lab_alias():
    """Preserve the draft record's proposed lab link while using a clear label."""
    return RedirectResponse("/ask", status_code=307)


@router.get("/api/civic/status")
def civic_status(request: Request):
    """Return snapshot coverage without exposing runtime paths or secrets."""
    return status(request)


@router.get("/api/civic/search")
def civic_search(request: Request, q: str = Query(min_length=3, max_length=1000)):
    """This transparent keyword baseline never calls a model."""
    return {
        "mode": "keyword",
        "sources": civic_store.search(request.app.state.civic_database, q, limit=5),
    }


def _fusion(keyword, vector):
    """Combine rankings without pretending BM25 and vector scores share a scale."""
    scores, records = {}, {}
    for ranking in (keyword, vector):
        for rank, chunk in enumerate(ranking, start=1):
            identifier = chunk["chunk_id"]
            records[identifier] = chunk
            scores[identifier] = scores.get(identifier, 0) + 1 / (60 + rank)
    return [
        {**records[identifier], "fusion_score": scores[identifier]}
        for identifier in sorted(scores, key=lambda item: (-scores[item], item))[:5]
    ]


def _retrieval(request, question, provider):
    database = request.app.state.civic_database
    keyword = civic_store.search(database, question, limit=5)
    index = civic_vectors.index_status(database, provider["embedding_model"])
    if not index["compatible"] or not index["indexed_chunks"]:
        return keyword, "keyword"
    vector = civic_ai.embed_texts([question])[0]
    keyword = _current_chunks(database, keyword)
    semantic = civic_vectors.search_vectors(
        database, vector, provider["embedding_model"], limit=5
    )
    return _fusion(keyword, semantic), "hybrid"


def _current_chunks(database, chunks):
    """Reject a changed evidence version instead of silently citing stale text."""
    current = civic_store.get_chunks(database, [row["chunk_id"] for row in chunks])
    if len(current) != len(chunks) or any(
        fresh["content_hash"] != old["content_hash"]
        for fresh, old in zip(current, chunks)
    ):
        raise HTTPException(
            409,
            "The source records changed while answering. "
            "Please submit the question again.",
        )
    return current


def _answer(request, question):
    """Paid calls only occur for an explicit AI request with server opt-in."""
    database = request.app.state.civic_database
    if question.mode == "search":
        chunks = civic_store.search(database, question.question, limit=5)
        return {
            "mode": "source_search",
            "retrieval": "keyword",
            "answer": (
                "These are matching passages from the saved official records. "
                "This is source search, not an AI-generated answer."
                if chunks
                else "I could not find supporting information in the imported records. "
                "This small snapshot does not contain all Newark information."
            ),
            "sources": chunks,
            "insufficient_evidence": not bool(chunks),
            "model": None,
        }
    provider = civic_ai.configuration_status()
    if not request.app.state.civic_allow_ai or not provider["configured"]:
        raise HTTPException(
            503,
            "AI answers are not connected yet. Source search works while the "
            "operator configures the API key privately.",
        )
    with civic_limits.one_request():
        try:
            chunks, method = _retrieval(request, question.question, provider)
            if not chunks:
                return {
                    "mode": "insufficient_evidence",
                    "retrieval": method,
                    "answer": (
                        "The imported records do not support an answer. "
                        "Please check the official city source for information "
                        "outside this snapshot."
                    ),
                    "sources": [],
                    "insufficient_evidence": True,
                    "model": None,
                }
            chunks = _current_chunks(database, chunks)
            result = civic_ai.generate_answer(question.question, chunks)
            chunks = _current_chunks(database, chunks)
        except (civic_ai.ModelNotConfigured, civic_ai.ModelServiceError) as error:
            raise HTTPException(503, str(error)) from None
        except civic_vectors.VectorIndexUnavailable:
            raise HTTPException(
                503, "The search index is temporarily unavailable. Try source search."
            ) from None
    cited = set(result["citation_ids"])
    return {
        **result,
        "mode": "ai",
        "retrieval": method,
        "sources": [chunk for chunk in chunks if chunk["chunk_id"] in cited],
    }


async def _question(request):
    """Bound bytes before JSON parsing, including requests without Content-Length."""
    body = bytearray()
    async for block in request.stream():
        body.extend(block)
        if len(body) > 4096:
            raise HTTPException(413, "Submit a question of at most 1,000 characters.")
    try:
        return Question.model_validate(json.loads(body))
    except (ValidationError, ValueError, UnicodeDecodeError):
        raise HTTPException(
            422, "Submit a question of 3 to 1,000 characters."
        ) from None


@router.post("/api/civic/chat")
async def civic_chat(request: Request):
    """Queries stay out of logs/database; no account or private content is indexed."""
    api_csrf(request)
    question = await _question(request)
    # Hash the direct peer address; do not trust arbitrary forwarded headers.
    peer = request.client.host if request.client else "unknown"
    bucket = hashlib.sha256(peer.encode()).hexdigest()
    civic_limits.consume(request.app.state.civic_database, bucket)
    result = await run_in_threadpool(_answer, request, question)
    result["checked_at"] = datetime.now(ZoneInfo("America/New_York")).isoformat()
    return result


@router.post("/api/civic/import")
async def civic_import(request: Request):
    """Only a current admin may refresh the fixed, bounded official feed."""
    security.require_admin(request)
    api_csrf(request)
    body = bytearray()
    async for block in request.stream():
        body.extend(block)
        if len(body) > 100:
            raise HTTPException(413, "Submit only a limit between 1 and 5.")
    try:
        values = json.loads(body)
        limit = values["limit"]
        if (
            set(values) != {"limit"}
            or isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 5
        ):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise HTTPException(422, "Submit only a limit between 1 and 5.") from None
    today = datetime.now(ZoneInfo("America/New_York")).date()
    with civic_limits.one_request():
        try:
            return await run_in_threadpool(
                civic_etl.run_import, request.app.state.civic_database, today, limit
            )
        except civic_etl.CivicImportError:
            raise HTTPException(
                503,
                "The official feed could not be refreshed. Saved records were kept.",
            ) from None
