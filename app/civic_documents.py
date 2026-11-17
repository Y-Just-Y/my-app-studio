"""Import only hash-bound, reviewed facts from one official introduced-budget PDF.

The scan is not automatically OCRed into trusted facts. A changed PDF requires
another review; failed verification returns no documents and changes no storage.
"""

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from time import monotonic

import httpx

from app import civic_store

PDF_URL = (
    "https://www.newarknj.gov/DocumentCenter/View/3062/"
    "2026-City-of-Newark-Introduced--Legal-Line-Budget-"
)
PDF_SHA256 = "dd9387451debf0b36c79d84e8d37fcc85466e823d4627bd5f0b04e82ab304474"
MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_FETCH_SECONDS = 30
SUMMARY_SOURCE_ID = "newark-budget-2026-introduced-summary"
STATUS_SOURCE_ID = "newark-budget-2026-introduced-status"
EXTRACT_PATH = Path(__file__).with_name("data") / "newark_2026_introduced_budget.json"
AMOUNT_KEYS = (
    "total_general_exclusive",
    "reserve",
    "total_general_including_reserve",
    "municipal_taxation",
)


class DocumentFetchError(RuntimeError):
    """The fixed official PDF could not be safely fetched or read."""


class DocumentReviewRequired(RuntimeError):
    """The PDF differs from the reviewed bytes and cannot refresh saved facts."""


def _read_extract():
    """Read the committed public extract and reject inconsistent provenance."""
    extract = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
    source = extract["source"]
    expected = {
        "url": PDF_URL,
        "sha256": PDF_SHA256,
        "year": 2026,
        "status": "introduced",
        "introduced_date": None,
    }
    if source["adoption_verified"] is not False or any(
        source.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("The reviewed budget extract has inconsistent provenance.")
    amounts = {key: Decimal(extract["amounts"][key]["value"]) for key in AMOUNT_KEYS}
    if (
        amounts["total_general_exclusive"] + amounts["reserve"]
        != amounts["total_general_including_reserve"]
        or amounts["total_general_including_reserve"]
        - Decimal(extract["additional_rows"]["anticipated_revenues"]["value"])
        != amounts["municipal_taxation"]
    ):
        raise ValueError("The reviewed budget summary does not reconcile.")
    return extract


def _reviewed_documents(data):
    """Construct two semantic passages only when the complete bytes match review."""
    if not data.startswith(b"%PDF-"):
        raise DocumentFetchError("The official budget response was not a PDF.")
    if hashlib.sha256(data).hexdigest() != PDF_SHA256:
        raise DocumentReviewRequired(
            "The official budget PDF changed and requires review; "
            "prior verified facts must be retained."
        )
    extract = _read_extract()
    raw = {key: extract["amounts"][key]["raw"] for key in AMOUNT_KEYS}
    values = {key: extract["amounts"][key]["value"] for key in AMOUNT_KEYS}
    summary = (
        "Newark 2026 INTRODUCED municipal budget: selected summary figures in USD.\n"
        "Source: PDF page 1 (unprinted computation sheet), corroborated by PDF "
        "page 6, printed Sheet 3, YEAR 2026 column.\n"
        f"Total General Appropriations EXCLUSIVE of Reserve for Uncollected Taxes: "
        f"${raw['total_general_exclusive']} USD.\n"
        f"Reserve for Uncollected Taxes: ${raw['reserve']} USD.\n"
        f"Total General Appropriations INCLUDING that reserve: "
        f"${raw['total_general_including_reserve']} USD.\n"
        "Total Anticipated Revenues: "
        f"${extract['additional_rows']['anticipated_revenues']['raw']} USD.\n"
        f"Amount to Be Raised by Taxation in Municipal Budget: "
        f"${raw['municipal_taxation']} USD.\n"
        "The separate "
        f"${extract['additional_rows']['taxation_including_other_taxes']['raw']} "
        "total includes other taxes and is NOT the "
        "municipal-budget taxation amount.\n"
        "These are introduced-budget figures, not an approved or adopted total. "
        "No introduction date or adoption evidence is established by this extract."
    )
    status = (
        "Newark 2026 INTRODUCED municipal budget: status and date limits. "
        "The official source filename identifies an introduced budget.\n"
        "PDF page 3, printed Sheet 1: the Certification of Adopted Budget is an "
        "unfilled form; its date and certification fields are blank. "
        "PDF page 4, printed Sheet 2: the Municipal Budget Notice has blank "
        "resolution/approval/hearing dates and recorded-vote fields.\n"
        "An introduction date is unknown, and no adoption date or adopted "
        "resolution is verified. The preprinted approved-budget heading on PDF "
        "page 6, Sheet 3, is not adoption evidence. Do not label the 2026 USD "
        "summary figures as an approved budget.\n"
        "Coverage is limited to reviewed summary/status facts on PDF pages "
        "1, 3, 4 and 6 of 105; the remaining pages are not indexed. "
        "AI-assisted OCR and visual verification are disclosed; this is not "
        "human peer approval or an exhaustive search for later adoption records."
    )
    metadata = {
        "kind": "budget",
        "status": "introduced",
        "year": 2026,
        "currency": "USD",
        "publisher": "City of Newark",
        "source_sha256": PDF_SHA256,
        "source_url": PDF_URL,
        "pdf_page_count": 105,
        "reviewed_at": extract["review"]["reviewed_at"],
        "review_method": extract["review"]["method"],
        "reviewer_type": extract["review"]["reviewer_type"],
        "coverage": extract["review"]["coverage"],
        "introduced_date": None,
        "adoption_date": None,
        "adoption_verified": False,
        "verification": "Exact PDF SHA-256 matches the reviewed public extract.",
    }
    fetched_at = datetime.now(timezone.utc).isoformat()
    documents = []
    for source_id, page, heading, text, details in (
        (
            SUMMARY_SOURCE_ID,
            1,
            "2026 introduced budget amounts and municipal taxation (USD)",
            summary,
            {
                **values,
                "raw_amounts": raw,
                "printed_page_label": None,
                "supporting_pdf_pages": [6],
                "supporting_printed_page_labels": ["Sheet 3"],
                "status_pdf_pages": [3, 4],
            },
        ),
        (
            STATUS_SOURCE_ID,
            3,
            "2026 introduced budget: unknown introduction date, no adoption proof",
            status,
            {"printed_page_label": "Sheet 1", "supporting_pdf_pages": [4, 6]},
        ),
    ):
        if len(text) > 1600:
            raise ValueError("Reviewed budget passages must fit one semantic chunk.")
        documents.append(
            {
                "source_id": source_id,
                "title": "Newark 2026 introduced municipal budget — " + heading,
                "url": f"{PDF_URL}#page={page}",
                "heading": heading,
                "text": text,
                "fetched_at": fetched_at,
                "source_updated_at": None,
                "metadata": {**metadata, "pdf_page": page, **details},
            }
        )
    return documents


def documents_from_pdf(path):
    """Verify a local PDF against the reviewed hash without network or paid calls."""
    try:
        local_pdf = Path(path)
        if not local_pdf.is_file():
            raise OSError("Expected a regular PDF file.")
        with local_pdf.open("rb") as source:
            data = source.read(MAX_PDF_BYTES + 1)
    except OSError as error:
        raise DocumentFetchError("The local budget PDF could not be read.") from error
    if len(data) > MAX_PDF_BYTES:
        raise DocumentFetchError("The budget PDF exceeds the bounded size limit.")
    return _reviewed_documents(data)


def _fetch(client):
    """Fetch exactly one fixed URL, with redirects disabled and bounded body bytes."""
    deadline = monotonic() + MAX_FETCH_SECONDS
    try:
        with client.stream(
            "GET",
            PDF_URL,
            follow_redirects=False,
            timeout=httpx.Timeout(15, connect=8),
        ) as response:
            if response.status_code != 200:
                raise DocumentFetchError(
                    f"The official budget PDF returned HTTP {response.status_code}."
                )
            if response.headers.get("content-type", "").split(";")[
                0
            ].lower().strip() != ("application/pdf"):
                raise DocumentFetchError("The official response was not a PDF type.")
            length = response.headers.get("content-length")
            if length is not None:
                try:
                    length = int(length)
                except ValueError as error:
                    raise DocumentFetchError("Invalid PDF length header.") from error
                if length < 0 or length > MAX_PDF_BYTES:
                    raise DocumentFetchError("The budget PDF exceeds the size limit.")
            data = bytearray()
            for part in response.iter_bytes():
                if monotonic() > deadline:
                    raise DocumentFetchError(
                        "The budget PDF fetch exceeded its time limit."
                    )
                if len(data) + len(part) > MAX_PDF_BYTES:
                    raise DocumentFetchError("The budget PDF exceeds the size limit.")
                data.extend(part)
    except httpx.HTTPError as error:
        raise DocumentFetchError("The official budget PDF request failed.") from error
    return _reviewed_documents(bytes(data))


def fetch_documents(*, client=None):
    """Fetch and verify one official scan; failures never update saved facts."""
    if client is not None:
        return _fetch(client)
    with httpx.Client(timeout=httpx.Timeout(25, connect=8)) as connection:
        return _fetch(connection)


def budget_snapshot(database):
    """Read the stored reviewed summary; its verification time is not adoption."""
    source = civic_store.get_source(database, SUMMARY_SOURCE_ID)
    if source is None:
        return {"available": False}
    metadata = source["metadata"]
    if (
        metadata.get("kind") != "budget"
        or metadata.get("status") != "introduced"
        or metadata.get("source_sha256") != PDF_SHA256
    ):
        return {"available": False}
    return {
        "available": True,
        "year": 2026,
        "status": "introduced",
        "adoption_verified": False,
        "introduced_date": None,
        "adoption_date": None,
        **{key: metadata[key] for key in AMOUNT_KEYS},
        "raw_amounts": metadata["raw_amounts"],
        "currency": "USD",
        "source_url": source["url"],
        "pdf_page": 1,
        "supporting_pdf_pages": [6],
        "status_pdf_pages": [3, 4],
        "reviewed_at": metadata["reviewed_at"],
        "checked_at": metadata["reviewed_at"],
        "fetched_at": source["fetched_at"],
        "source_sha256": PDF_SHA256,
        "coverage": metadata["coverage"],
    }
