"""Bounded Extract/Transform/Load for Newark's public Legistar meeting records.

The City Clerk links Newark's Legistar agenda service. This importer requests
public JSON metadata, retains attribution, and never crawls testimony or PDFs.
"""

from datetime import date, datetime, time, timedelta, timezone
import hashlib
import html
import json
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from app import civic_store

API_ROOT = "https://webapi.legistar.com/v1/newark"
CITY_CLERK_URL = "https://www.newarknj.gov/166/Office-of-the-City-Clerk"
MEETING_TIMEZONE = "America/New_York"
MAX_RESPONSE_BYTES = 2_000_000
MAX_MEETINGS = 10
MAX_AGENDA_ITEMS = 2
ALLOWED_AGENDA_TYPES = {"Ordinance", "Resolution"}
AGENDA_TOPICS = re.compile(
    r"\b(ordinance|budget|appropriat|grant|abatement|infrastructure|"
    r"transportation|park|water|sewer|housing|redevelopment)",
    re.IGNORECASE,
)
EXCLUDED_AGENDA_TOPICS = re.compile(
    r"\b(refund|settlement|personnel|employee|honorary|tuition|claim|"
    r"litigation|license|citizen|testimony)\b",
    re.IGNORECASE,
)


class CivicImportError(ValueError):
    """A source problem must leave the last successful import intact."""


def _plain(value, maximum=2_000):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CivicImportError("The public feed contained an invalid text field.")
    text = html.unescape(re.sub(r"<[^>]+>", " ", value))
    cleaned = " ".join(text.split())
    if len(cleaned) > maximum:
        raise CivicImportError("A public source field exceeded the import size cap.")
    return cleaned


def _positive_id(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CivicImportError("The public feed contained an invalid record ID.")
    return value


def _fetch(client, endpoint, params, *, single=False):
    """Only the fixed Newark API is requested; redirects cannot widen the scope."""
    if not re.fullmatch(
        r"events(?:/[1-9][0-9]*(?:/eventitems)?)?|eventitems/[1-9][0-9]*", endpoint
    ):
        raise CivicImportError("This importer only reads Newark meeting metadata.")
    url = f"{API_ROOT}/{endpoint}"
    try:
        with client.stream(
            "GET", url, params=params, follow_redirects=False
        ) as response:
            response.raise_for_status()
            if single and response.status_code != 200:
                raise CivicImportError(
                    "The official API record did not return a complete response."
                )
            if response.is_redirect:
                raise CivicImportError(
                    "The source redirected; inspect it before importing."
                )
            parts = []
            length = 0
            for part in response.iter_bytes():
                length += len(part)
                if length > MAX_RESPONSE_BYTES:
                    raise CivicImportError(
                        "The public feed exceeded the import size cap."
                    )
                parts.append(part)
            raw = b"".join(parts)
            value = json.loads(raw)
            valid = (
                isinstance(value, dict)
                if single
                else (
                    isinstance(value, list)
                    and all(isinstance(row, dict) for row in value)
                )
            )
            if not valid:
                raise CivicImportError(
                    "The public feed had an unexpected record format."
                )
            return value, str(response.url), hashlib.sha256(raw).hexdigest()
    except httpx.HTTPError:
        raise CivicImportError(
            "Newark's public feed could not be fetched. Existing records were kept."
        ) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise CivicImportError("The public feed did not contain valid JSON.") from None


def _meeting_date(event):
    try:
        value = datetime.fromisoformat(event["EventDate"]).date()
    except (KeyError, TypeError, ValueError):
        raise CivicImportError(
            "The public feed contained an invalid meeting date."
        ) from None
    return value


def _meeting_url(event):
    url = event.get("EventInSiteURL", "")
    if not isinstance(url, str):
        raise CivicImportError("The meeting did not contain an official source URL.")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "newark.legistar.com"
        or any((parsed.username, parsed.password))
        or parsed.port not in (None, 443)
        or parsed.path.lower() != "/meetingdetail.aspx"
    ):
        raise CivicImportError("The meeting URL was outside the official agenda site.")
    return url


def _verify_api_record(client, endpoint, identity, identifier):
    """A fallback must be a fetched official record with the expected identity."""
    record, api_url, _response_hash = _fetch(client, endpoint, {}, single=True)
    if _positive_id(record.get(identity)) != identifier:
        raise CivicImportError("The fallback source did not match the meeting record.")
    return api_url, record


def _verified_meeting_link(client, event, checked_at):
    """Check the original page; only a confirmed 404/410 permits an API fallback."""
    original = _meeting_url(event)
    try:
        with client.stream(
            "GET",
            original,
            follow_redirects=False,
            timeout=httpx.Timeout(12, connect=5),
        ) as response:
            original_status = response.status_code
    except httpx.HTTPError:
        raise CivicImportError(
            "The official source link could not be checked. Existing records were kept."
        ) from None
    metadata = {
        "original_page_url": original,
        "original_http_status": original_status,
        "link_checked_at": checked_at,
        "link_resolution": "verified_original_page",
    }
    if original_status == 200:
        return original, metadata
    if original_status not in (404, 410):
        raise CivicImportError(
            "The official source page is unavailable. Existing records were kept."
        )
    identifier = _positive_id(event.get("EventId"))
    api_url, record = _verify_api_record(
        client, f"events/{identifier}", "EventId", identifier
    )
    if record.get("EventBodyName") != event.get("EventBodyName") or _meeting_date(
        record
    ) != _meeting_date(event):
        raise CivicImportError("The fallback source did not match the meeting record.")
    metadata["link_resolution"] = "verified_official_api_record"
    return api_url, metadata


def _time_metadata(meeting_day, displayed_time):
    """The API date is local civic-calendar time, not an implicit UTC instant."""
    try:
        parsed = datetime.strptime(displayed_time, "%I:%M %p").time()
    except ValueError:
        return {"meeting_starts_at": None}
    starts = datetime.combine(meeting_day, parsed, tzinfo=ZoneInfo(MEETING_TIMEZONE))
    return {"meeting_starts_at": starts.isoformat()}


def _meeting_document(event, fetched_at, api_url, response_hash):
    identifier = _positive_id(event.get("EventId"))
    day = _meeting_date(event)
    body = _plain(event.get("EventBodyName"), 200)
    if body != "Municipal Council":
        raise CivicImportError("An unexpected civic body appeared in the bounded feed.")
    meeting_time = _plain(event.get("EventTime"), 80) or "Time not supplied"
    location = _plain(event.get("EventLocation"), 500) or "Location not supplied"
    agenda_status = _plain(event.get("EventAgendaStatusName"), 80) or "Not supplied"
    readable_day = f"{day.strftime('%B')} {day.day}, {day.year}"
    title = f"Newark Municipal Council meeting — {readable_day}"
    text = (
        f"{title}\n"
        f"Meeting date: {day.isoformat()} ({readable_day}).\n"
        f"Scheduled time: {meeting_time}, {MEETING_TIMEZONE}.\n"
        f"Location: {location}.\n"
        f"Agenda publication status: {agenda_status}.\n\n"
        "This is an imported public meeting record. A scheduled meeting or final "
        "agenda does not establish that a meeting occurred or an item passed. "
        "Consult the linked official record for current details and minutes."
    )
    metadata = {
        "kind": "meeting",
        "publisher": "City of Newark / Legistar",
        "city_clerk_url": CITY_CLERK_URL,
        "api_url": api_url,
        "response_sha256": response_hash,
        "event_id": identifier,
        "meeting_date": day.isoformat(),
        "meeting_date_display": readable_day,
        "meeting_time": meeting_time,
        "timezone": MEETING_TIMEZONE,
        "body": body,
        "location": location,
        "agenda_status": agenda_status,
        "source_access": "Public official API metadata; attribution retained.",
        **_time_metadata(day, meeting_time),
    }
    return {
        "source_id": f"newark-meeting-{identifier}",
        "title": title,
        "url": _meeting_url(event),
        "heading": "Meeting schedule and official agenda record",
        "text": text,
        "source_updated_at": event.get("EventLastModifiedUtc"),
        "metadata": metadata,
        "fetched_at": fetched_at,
    }


def _agenda_document(item, meeting, fetched_at, api_url, response_hash):
    identifier = _positive_id(item.get("EventItemId"))
    title = _plain(item.get("EventItemTitle"))
    matter_type = _plain(item.get("EventItemMatterType"), 100)
    if (
        matter_type not in ALLOWED_AGENDA_TYPES
        or not AGENDA_TOPICS.search(title)
        or EXCLUDED_AGENDA_TOPICS.search(title)
    ):
        return None
    matter_id = _positive_id(item.get("EventItemMatterId"))
    file_number = _plain(item.get("EventItemMatterFile"), 80)
    status = _plain(item.get("EventItemMatterStatus"), 100) or "Not supplied"
    metadata = {
        key: meeting["metadata"][key]
        for key in (
            "meeting_date",
            "event_id",
            "body",
            "timezone",
            "publisher",
            "original_page_url",
            "original_http_status",
            "link_checked_at",
            "link_resolution",
        )
    }
    metadata.update(
        {
            "kind": "agenda_item",
            "event_item_id": identifier,
            "matter_id": matter_id,
            "matter_file": file_number,
            "matter_type": matter_type,
            "matter_status": status,
            "api_url": api_url,
            "response_sha256": response_hash,
            "source_access": "Public official API metadata; attribution retained.",
        }
    )
    text = (
        f"Newark Municipal Council agenda item {file_number}.\n"
        f"Meeting date: {metadata['meeting_date']}.\n"
        f"Record type: {matter_type}.\n"
        f"Title: {title}\n"
        f"Matter status reported by the source: {status}.\n\n"
        "An agenda listing is not evidence of final passage. This limited import "
        "does not include voting histories, full legislation, attachments or minutes."
    )
    return {
        "source_id": f"newark-agenda-{identifier}",
        "title": f"{file_number} · {title[:180]}",
        "url": meeting["url"],
        "heading": f"{matter_type} agenda item {file_number}",
        "text": text,
        "source_updated_at": item.get("EventItemLastModifiedUtc"),
        "metadata": metadata,
        "fetched_at": fetched_at,
    }


def _agenda_documents(client, meeting, fetched_at):
    event_id = meeting["metadata"]["event_id"]
    items, agenda_url, agenda_hash = _fetch(
        client, f"events/{event_id}/eventitems", {"$top": 100}
    )
    if len(items) > 100:
        raise CivicImportError("The source exceeded the agenda-item page limit.")
    documents = []
    for item in items:
        document = _agenda_document(item, meeting, fetched_at, agenda_url, agenda_hash)
        if document:
            if meeting["metadata"]["original_http_status"] in (404, 410):
                identifier = document["metadata"]["event_item_id"]
                api_url, record = _verify_api_record(
                    client, f"eventitems/{identifier}", "EventItemId", identifier
                )
                if record.get("EventItemEventId") != event_id:
                    raise CivicImportError(
                        "The fallback agenda source did not match its meeting."
                    )
                document["url"] = api_url
            documents.append(document)
            if len(documents) >= MAX_AGENDA_ITEMS:
                break
    return documents


def _extract(client, as_of, limit, fetched_at):
    cutoff = datetime.combine(as_of + timedelta(days=1), time.min).isoformat()
    events, api_url, response_hash = _fetch(
        client,
        "events",
        {
            "$filter": f"EventDate lt datetime'{cutoff}' "
            "and EventBodyName eq 'Municipal Council'",
            "$orderby": "EventDate desc,EventId desc",
            "$top": limit,
        },
    )
    if len(events) > limit:
        raise CivicImportError("The source exceeded the requested meeting limit.")
    documents = []
    for event in events:
        if _meeting_date(event) > as_of:
            raise CivicImportError(
                "A future meeting appeared in the recent-meeting query."
            )
        document = _meeting_document(event, fetched_at, api_url, response_hash)
        document["url"], link_metadata = _verified_meeting_link(
            client, event, fetched_at
        )
        document["metadata"].update(link_metadata)
        documents.append(document)
    if documents:
        documents.extend(_agenda_documents(client, documents[0], fetched_at))
    return documents


def fetch_documents(as_of, limit=5, *, client=None):
    """Extract public records and transform fields; do not write until all succeed."""
    if not isinstance(as_of, date) or not 1 <= limit <= MAX_MEETINGS:
        raise ValueError("Choose an as-of date and between 1 and 10 recent meetings.")
    fetched_at = datetime.now(timezone.utc).isoformat()
    if client is not None:
        return _extract(client, as_of, limit, fetched_at)
    with httpx.Client(
        timeout=httpx.Timeout(20, connect=5),
        follow_redirects=False,
        headers={"User-Agent": "NewarkCivicPulse-classroom-import/1.0"},
    ) as source:
        return _extract(source, as_of, limit, fetched_at)


def run_import(path, as_of, limit=5, *, client=None):
    """Commit one complete successful import; partial network results are discarded."""
    documents = fetch_documents(as_of, limit, client=client)
    counters = civic_store.upsert_documents(path, documents)
    status = civic_store.snapshot(path)
    return {
        "source": API_ROOT,
        "as_of": as_of.isoformat(),
        "api_key_required_for_this_verified_read": False,
        "extract": {
            "meetings": sum(d["metadata"]["kind"] == "meeting" for d in documents),
            "agenda_items": sum(
                d["metadata"]["kind"] == "agenda_item" for d in documents
            ),
        },
        "transform": {
            "documents": len(documents),
            "chunking": civic_store.CHUNKING_METHOD,
            "units": "Unicode characters, not model tokens",
        },
        "load": counters,
        "sources": status["sources"],
        "chunks": status["chunks"],
        "last_fetched_at": status["last_fetched_at"],
        "limitations": [
            "Bounded snapshot of recent records, not a complete calendar or live feed.",
            "Agenda listing/publication status does not establish "
            "meeting occurrence or passage.",
            "No voting histories, testimony, attachments, private data or PDF crawl.",
        ],
    }
