"""Budget import checks use synthetic reviewed bytes and isolated local stores."""

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from app import civic_documents, civic_store
from app.civic_refresh import writer_lock
import civic_budget_import


@pytest.fixture(name="reviewed_pdf")
def reviewed_pdf_fixture(tmp_path, monkeypatch):
    """Give transport tests a hash-bound synthetic file, not a live city request."""
    data = b"%PDF-1.4\ncontrolled synthetic reviewed PDF fixture\n%%EOF\n"
    extract = json.loads(civic_documents.EXTRACT_PATH.read_text(encoding="utf-8"))
    extract["source"]["sha256"] = hashlib.sha256(data).hexdigest()
    extract["source"]["bytes"] = len(data)
    manifest = tmp_path / "reviewed.json"
    manifest.write_text(json.dumps(extract), encoding="utf-8")
    monkeypatch.setattr(civic_documents, "EXTRACT_PATH", manifest)
    monkeypatch.setattr(civic_documents, "PDF_SHA256", extract["source"]["sha256"])
    return data


def budget_client(data, *, status=200, headers=None, follow_redirects=False):
    """Return only the fixed official endpoint from a controlled transport."""
    response_headers = {"content-type": "application/pdf", **(headers or {})}

    def respond(request):
        assert str(request.url) == civic_documents.PDF_URL
        assert request.method == "GET"
        return httpx.Response(status, headers=response_headers, content=data)

    return httpx.Client(
        transport=httpx.MockTransport(respond), follow_redirects=follow_redirects
    )


def test_packaged_extract_preserves_financial_meaning():
    """The four reviewed totals keep their labels, raw digits and exact dollar units."""
    extract = civic_documents._read_extract()  # pylint: disable=protected-access
    expected = {
        "total_general_exclusive": "880149264.94",
        "reserve": "20351000.00",
        "total_general_including_reserve": "900500264.94",
        "municipal_taxation": "288267071.55",
    }
    assert {
        key: value["value"] for key, value in extract["amounts"].items()
    } == expected
    assert extract["amounts"]["municipal_taxation"]["raw"] == "288,267,071.55"
    assert extract["source"]["page_count"] == 105
    assert extract["source"]["introduced_date"] is None
    assert extract["source"]["adoption_verified"] is False
    assert extract["page_labels"] == {
        "1": None,
        "3": "Sheet 1",
        "4": "Sheet 2",
        "6": "Sheet 3",
    }
    assert extract["review"]["visual_review_pdf_pages"] == [1, 3, 4, 6]
    assert all(
        0 <= line["confidence"] <= 1 and len(line["box"]) == 4
        for page in extract["ocr_evidence"]
        for line in page["observations"]
    )


def test_fixed_remote_pdf_produces_two_page_aware_chunks(reviewed_pdf):
    """No paid call or arbitrary source input is needed for the reviewed passages."""
    with budget_client(reviewed_pdf) as client:
        documents = civic_documents.fetch_documents(client=client)
        assert not client.is_closed
    assert {row["source_id"] for row in documents} == {
        civic_documents.SUMMARY_SOURCE_ID,
        civic_documents.STATUS_SOURCE_ID,
    }
    assert [row["url"] for row in documents] == [
        civic_documents.PDF_URL + "#page=1",
        civic_documents.PDF_URL + "#page=3",
    ]
    assert all(len(row["text"]) <= 1600 for row in documents)
    assert all(
        "2026" in row["text"] and "INTRODUCED" in row["text"] for row in documents
    )
    assert all("USD" in row["text"] and "PDF page" in row["text"] for row in documents)
    assert all(row["metadata"]["kind"] == "budget" for row in documents)
    assert all(row["metadata"]["status"] == "introduced" for row in documents)
    assert "INCLUDING that reserve: $900,500,264.94 USD" in documents[0]["text"]
    assert "not adoption evidence" in documents[1]["text"]
    assert all(row["source_updated_at"] is None for row in documents)


@pytest.mark.parametrize("status", [302, 403, 404, 500])
def test_http_failures_are_not_successful_imports(reviewed_pdf, status):
    """An error body must not become evidence or leak into status messages."""
    with budget_client(b"private error detail", status=status) as client:
        with pytest.raises(civic_documents.DocumentFetchError) as error:
            civic_documents.fetch_documents(client=client)
    assert str(status) in str(error.value)
    assert "private error detail" not in str(error.value)
    assert reviewed_pdf.startswith(b"%PDF-")


def test_redirects_are_not_followed_even_for_redirecting_client(reviewed_pdf):
    """A fixed source cannot redirect the adapter to another network endpoint."""
    with budget_client(
        reviewed_pdf,
        status=302,
        headers={"location": "https://unapproved.example/other.pdf"},
        follow_redirects=True,
    ) as client:
        with pytest.raises(civic_documents.DocumentFetchError, match="HTTP 302"):
            civic_documents.fetch_documents(client=client)


@pytest.mark.parametrize(
    "headers",
    [
        {"content-type": "text/html"},
        {"content-length": "9000000"},
        {"content-length": "-1"},
        {"content-length": "not-a-length"},
    ],
)
def test_invalid_pdf_headers_are_rejected(reviewed_pdf, headers):
    """Type and declared byte limits are checked before trusting the document."""
    with budget_client(reviewed_pdf, headers=headers) as client:
        with pytest.raises(civic_documents.DocumentFetchError):
            civic_documents.fetch_documents(client=client)


def test_streamed_pdf_body_is_bounded_without_a_length(reviewed_pdf, monkeypatch):
    """Chunked responses cannot bypass the body limit through missing headers."""
    monkeypatch.setattr(civic_documents, "MAX_PDF_BYTES", 20)

    def respond(_request):
        return httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            stream=httpx.ByteStream(reviewed_pdf),
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(civic_documents.DocumentFetchError, match="size limit"):
            civic_documents.fetch_documents(client=client)


def test_changed_scan_requires_review_and_keeps_old_facts(reviewed_pdf, tmp_path):
    """A new hash cannot silently replace old numbers or their verification time."""
    database = tmp_path / "public.sqlite3"
    with budget_client(reviewed_pdf) as client:
        documents = civic_documents.fetch_documents(client=client)
    civic_store.upsert_documents(database, documents)
    before = civic_store.get_source(database, civic_documents.SUMMARY_SOURCE_ID)
    with budget_client(reviewed_pdf + b"changed scan") as client:
        with pytest.raises(
            civic_documents.DocumentReviewRequired, match="requires review"
        ):
            civic_documents.fetch_documents(client=client)
    with budget_client(b"denied", status=403) as client:
        with pytest.raises(civic_documents.DocumentFetchError):
            civic_documents.fetch_documents(client=client)
    assert civic_store.get_source(database, civic_documents.SUMMARY_SOURCE_ID) == before


def test_pdf_stream_has_a_total_time_bound(reviewed_pdf, monkeypatch):
    """A trickling source cannot keep the writer lock indefinitely."""
    clock = iter([0, civic_documents.MAX_FETCH_SECONDS + 1])
    monkeypatch.setattr(civic_documents, "monotonic", lambda: next(clock))
    with budget_client(reviewed_pdf) as client:
        with pytest.raises(civic_documents.DocumentFetchError, match="time limit"):
            civic_documents.fetch_documents(client=client)


def test_local_import_repeats_without_new_versions_or_chunks(reviewed_pdf, tmp_path):
    """Local reviewed files are explicit; repeated verification is idempotent."""
    path = tmp_path / "reviewed.pdf"
    path.write_bytes(reviewed_pdf)
    database = tmp_path / "public.sqlite3"
    documents = civic_documents.documents_from_pdf(path)
    assert civic_store.upsert_documents(database, documents) == {
        "inserted": 2,
        "updated": 0,
        "unchanged": 0,
    }
    chunks = civic_store.list_chunks(database)
    repeat = civic_documents.documents_from_pdf(path)
    assert civic_store.upsert_documents(database, repeat) == {
        "inserted": 0,
        "updated": 0,
        "unchanged": 2,
    }
    assert [row["chunk_id"] for row in civic_store.list_chunks(database)] == [
        row["chunk_id"] for row in chunks
    ]
    assert civic_store.snapshot(database)["chunks"] == 2
    answer = civic_store.search(database, "2026 budget total general appropriations")
    assert any("900,500,264.94" in row["text"] for row in answer)
    assert civic_store.search(database, "reset my account password") == []


def test_snapshot_exposes_reviewed_summary_without_adoption(reviewed_pdf, tmp_path):
    """The homepage can display exact decimal strings and the limits beside them."""
    database = tmp_path / "public.sqlite3"
    assert civic_documents.budget_snapshot(database) == {"available": False}
    with budget_client(reviewed_pdf) as client:
        civic_store.upsert_documents(
            database, civic_documents.fetch_documents(client=client)
        )
    snapshot = civic_documents.budget_snapshot(database)
    assert snapshot["available"]
    assert snapshot["status"] == "introduced"
    assert snapshot["introduced_date"] is None
    assert snapshot["adoption_verified"] is False
    assert snapshot["adoption_date"] is None
    assert snapshot["total_general_including_reserve"] == "900500264.94"
    assert snapshot["total_general_exclusive"] == "880149264.94"
    assert snapshot["reserve"] == "20351000.00"
    assert snapshot["municipal_taxation"] == "288267071.55"
    assert snapshot["pdf_page"] == 1
    assert snapshot["supporting_pdf_pages"] == [6]
    assert snapshot["source_sha256"] == civic_documents.PDF_SHA256
    assert snapshot["checked_at"] == snapshot["reviewed_at"]
    assert snapshot["raw_amounts"]["reserve"] == "20,351,000.00"


def test_local_unknown_or_non_pdf_cannot_import(reviewed_pdf, tmp_path):
    """Supplying a local file is not permission to trust unknown extracted text."""
    missing = tmp_path / "absent.pdf"
    with pytest.raises(civic_documents.DocumentFetchError):
        civic_documents.documents_from_pdf(missing)
    path = tmp_path / "wrong.pdf"
    path.write_bytes(b"<html>not a PDF</html>")
    with pytest.raises(civic_documents.DocumentFetchError):
        civic_documents.documents_from_pdf(path)
    path.write_bytes(reviewed_pdf + b"unreviewed")
    with pytest.raises(civic_documents.DocumentReviewRequired):
        civic_documents.documents_from_pdf(path)


def test_cli_local_import_and_repeat_are_explicit(reviewed_pdf, tmp_path, capsys):
    """The CLI reports storage counts and performs neither embeddings nor OCR."""
    path = tmp_path / "reviewed.pdf"
    path.write_bytes(reviewed_pdf)
    database = tmp_path / "public.sqlite3"
    arguments = ["--pdf", str(path), "--database", str(database)]
    assert civic_budget_import.main(arguments) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["local_pdf"] and first["documents"] == 2
    assert first["load"]["inserted"] == 2
    assert civic_budget_import.main(arguments) == 0
    assert json.loads(capsys.readouterr().out)["load"]["unchanged"] == 2
    path.write_bytes(reviewed_pdf + b"changed")
    assert civic_budget_import.main(arguments) == 1
    captured = capsys.readouterr()
    assert not captured.out and "requires review" in captured.err
    assert civic_store.snapshot(database)["sources"] == 2


def test_remote_network_errors_do_not_expose_transport_detail():
    """Only a sanitized error is shown for unavailable official infrastructure."""

    def fail(request):
        raise httpx.ConnectError("secret transport detail", request=request)

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(civic_documents.DocumentFetchError) as error:
            civic_documents.fetch_documents(client=client)
    assert "secret transport detail" not in str(error.value)


def test_manual_budget_import_respects_the_shared_writer_lock(
    reviewed_pdf, tmp_path, capsys
):
    """A manual budget command cannot race a nightly or admin refresh writer."""
    path = tmp_path / "reviewed.pdf"
    path.write_bytes(reviewed_pdf)
    database = tmp_path / "public.sqlite3"
    with writer_lock(database):
        assert (
            civic_budget_import.main(["--pdf", str(path), "--database", str(database)])
            == 1
        )
    captured = capsys.readouterr()
    assert not captured.out and "Budget import stopped" in captured.err
    assert not database.exists()


def test_reviewed_manifest_cannot_change_budget_status(tmp_path, monkeypatch):
    """A misleading approval flag is rejected even before source construction."""
    extract = json.loads(civic_documents.EXTRACT_PATH.read_text(encoding="utf-8"))
    extract["source"]["adoption_verified"] = True
    path = tmp_path / "incorrect.json"
    path.write_text(json.dumps(extract), encoding="utf-8")
    monkeypatch.setattr(civic_documents, "EXTRACT_PATH", Path(path))
    with pytest.raises(ValueError, match="inconsistent provenance"):
        civic_documents._read_extract()  # pylint: disable=protected-access
