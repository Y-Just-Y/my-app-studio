"""Versioned public civic records and a small SQLite FTS5 retrieval baseline.

This database contains public source material only. It is separate from the
application's account/session database and does not store questions or API keys.
"""

from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

from app.private_files import private_directory, private_file

MAX_DOCUMENT_CHARACTERS = 40_000
MAX_CHUNK_CHARACTERS = 1_600
MAX_BATCH_DOCUMENTS = 50
MAX_RESULTS = 10
CHUNKING_METHOD = "heading-paragraph-characters-v1"
SOURCE_HOSTS = {
    "newark.legistar.com",
    "webapi.legistar.com",
    "www.newarknj.gov",
    "newarknj.gov",
}
STOP_WORDS = set(
    "a an the and or to of for from in on at by with about it its this that these "
    "those i we you your me my our can could would should do does did is are was "
    "were be been have has had how what when where which who why please tell "
    "show give find know information data city newark civic municipal council "
    "meeting meetings agenda agendas event events most recent latest last next "
    "any there discussed discuss happened happen say says".split()
)
GENERIC_RECORD_WORDS = {
    "council",
    "meeting",
    "meetings",
    "agenda",
    "agendas",
    "event",
    "events",
}


@contextmanager
def _connection(path):
    database = Path(path)
    if database.is_symlink():
        raise ValueError("Civic storage must be an ordinary local database file.")
    with closing(sqlite3.connect(database, timeout=5)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection


def initialize(path):
    """Prepare a separate, private local file without modifying account tables."""
    database = Path(path)
    private_directory(database.parent)
    if database.is_symlink():
        raise ValueError("Civic storage must be an ordinary local database file.")
    with _connection(database) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS civic_sources (
                source_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                heading TEXT NOT NULL,
                text TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                source_updated_at TEXT,
                metadata TEXT NOT NULL,
                version INTEGER NOT NULL CHECK (version > 0)
            );
            CREATE TABLE IF NOT EXISTS civic_chunks (
                chunk_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES civic_sources(source_id)
                    ON DELETE CASCADE,
                ordinal INTEGER NOT NULL,
                heading TEXT NOT NULL,
                text TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                version INTEGER NOT NULL,
                UNIQUE(source_id, ordinal)
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS civic_fts USING fts5(
                chunk_id UNINDEXED, title, heading, text,
                tokenize='unicode61'
            );
            CREATE INDEX IF NOT EXISTS civic_chunks_source
                ON civic_chunks(source_id);
            """)
    private_file(database)


def _hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_document(document):
    required = ("source_id", "title", "url", "text", "heading", "fetched_at")
    if not isinstance(document, dict) or any(
        not isinstance(document.get(key), str) or not document[key].strip()
        for key in required
    ):
        raise ValueError(
            "Each source needs its ID, title, URL, heading, text and date."
        )
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,100}", document["source_id"]):
        raise ValueError("Source IDs must be short stable identifiers.")
    parsed = urlsplit(document["url"])
    if (
        parsed.scheme != "https"
        or parsed.hostname not in SOURCE_HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Civic sources must link to the allowed official publishers.")
    if parsed.hostname == "webapi.legistar.com" and (
        not re.fullmatch(r"/v1/newark/(?:events|eventitems)/[1-9][0-9]*", parsed.path)
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("API source links must identify one official Newark record.")
    if len(document["text"]) > MAX_DOCUMENT_CHARACTERS:
        raise ValueError("A source is larger than this bounded civic import permits.")
    if len(document["title"]) > 2_000 or len(document["heading"]) > 300:
        raise ValueError("The source title or heading is too long.")
    metadata = document.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("Source metadata must be an object.")
    return {
        **{key: document[key].strip() for key in required},
        "source_updated_at": document.get("source_updated_at"),
        "metadata": metadata,
    }


def _chunks(text):
    """Keep complete short civic records; split long paragraphs at word boundaries.

    The bound is Unicode characters, not tokenizer tokens. Embedding code must
    check its own model input limit before requesting embeddings.
    """
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    current = ""
    for paragraph in paragraphs:
        while len(paragraph) > MAX_CHUNK_CHARACTERS:
            if current:
                yield current
                current = ""
            boundary = paragraph.rfind(" ", 0, MAX_CHUNK_CHARACTERS + 1)
            boundary = boundary if boundary > 0 else MAX_CHUNK_CHARACTERS
            yield paragraph[:boundary].strip()
            paragraph = paragraph[boundary:].strip()
        if not paragraph:
            continue
        combined = current + "\n\n" + paragraph if current else paragraph
        if len(combined) > MAX_CHUNK_CHARACTERS:
            yield current
            current = paragraph
        else:
            current = combined
    if current:
        yield current


def upsert_documents(path, documents):
    """Atomically replace changed sources while leaving every other source intact."""
    if not isinstance(documents, list) or len(documents) > MAX_BATCH_DOCUMENTS:
        raise ValueError("Import a bounded list of public source documents.")
    checked = [_validate_document(document) for document in documents]
    identifiers = [document["source_id"] for document in checked]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("An import batch cannot repeat a source ID.")
    initialize(path)
    counts = {"inserted": 0, "updated": 0, "unchanged": 0}
    with _connection(path) as connection:
        for document in checked:
            metadata = json.dumps(document["metadata"], sort_keys=True)
            content_hash = _hash(
                json.dumps(
                    {key: document[key] for key in ("title", "url", "heading", "text")}
                    | {
                        "metadata": {
                            key: value
                            for key, value in document["metadata"].items()
                            if key
                            not in {
                                "api_url",
                                "response_sha256",
                                "link_checked_at",
                                "original_page_url",
                                "original_http_status",
                                "link_resolution",
                            }
                        },
                        "chunking": CHUNKING_METHOD,
                    },
                    sort_keys=True,
                )
            )
            existing = connection.execute(
                "SELECT version, content_hash FROM civic_sources WHERE source_id = ?",
                (document["source_id"],),
            ).fetchone()
            if existing and existing["content_hash"] == content_hash:
                connection.execute(
                    "UPDATE civic_sources SET fetched_at = ?, source_updated_at = ?, "
                    "metadata = ? "
                    "WHERE source_id = ?",
                    (
                        document["fetched_at"],
                        document["source_updated_at"],
                        metadata,
                        document["source_id"],
                    ),
                )
                counts["unchanged"] += 1
                continue
            version = existing["version"] + 1 if existing else 1
            connection.execute(
                "DELETE FROM civic_fts WHERE chunk_id IN "
                "(SELECT chunk_id FROM civic_chunks WHERE source_id = ?)",
                (document["source_id"],),
            )
            connection.execute(
                "DELETE FROM civic_chunks WHERE source_id = ?",
                (document["source_id"],),
            )
            connection.execute(
                """INSERT INTO civic_sources
                   (source_id,title,url,heading,text,content_hash,fetched_at,
                    source_updated_at,metadata,version)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(source_id) DO UPDATE SET
                     title=excluded.title,url=excluded.url,heading=excluded.heading,
                     text=excluded.text,content_hash=excluded.content_hash,
                     fetched_at=excluded.fetched_at,
                     source_updated_at=excluded.source_updated_at,
                     metadata=excluded.metadata,version=excluded.version""",
                (
                    document["source_id"],
                    document["title"],
                    document["url"],
                    document["heading"],
                    document["text"],
                    content_hash,
                    document["fetched_at"],
                    document["source_updated_at"],
                    metadata,
                    version,
                ),
            )
            for ordinal, text in enumerate(_chunks(document["text"]), 1):
                chunk_id = f"{document['source_id']}-v{version}-{ordinal:03}"
                connection.execute(
                    "INSERT INTO civic_chunks "
                    "(chunk_id,source_id,ordinal,heading,text,content_hash,version) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        chunk_id,
                        document["source_id"],
                        ordinal,
                        document["heading"],
                        text,
                        _hash(document["heading"] + "\n" + text),
                        version,
                    ),
                )
                connection.execute(
                    "INSERT INTO civic_fts(chunk_id,title,heading,text) "
                    "VALUES(?,?,?,?)",
                    (chunk_id, document["title"], document["heading"], text),
                )
            counts["updated" if existing else "inserted"] += 1
    return counts


_CHUNK_SELECT = """
    SELECT c.chunk_id, c.source_id, s.title, c.heading, c.text, s.url,
           s.fetched_at, s.source_updated_at, s.metadata, c.content_hash,
           s.content_hash AS source_hash, c.version
    FROM civic_chunks AS c JOIN civic_sources AS s ON s.source_id=c.source_id
"""


def _chunk_row(row, score=0.0):
    result = dict(row)
    result["metadata"] = json.loads(result["metadata"])
    result["score"] = float(score)
    return result


def list_chunks(path):
    """Return current public chunks for an optional separately managed vector index."""
    if not Path(path).exists():
        return []
    with _connection(path) as connection:
        return [
            _chunk_row(row)
            for row in connection.execute(_CHUNK_SELECT + " ORDER BY c.chunk_id")
        ]


def get_chunks(path, identifiers):
    """Resolve only current IDs, so deleted versions cannot enter answer context."""
    identifiers = list(dict.fromkeys(identifiers))[:100]
    if not identifiers or not Path(path).exists():
        return []
    placeholders = ",".join("?" for _ in identifiers)
    with _connection(path) as connection:
        rows = connection.execute(
            _CHUNK_SELECT + f" WHERE c.chunk_id IN ({placeholders})", identifiers
        ).fetchall()
    by_id = {row["chunk_id"]: _chunk_row(row) for row in rows}
    return [by_id[identifier] for identifier in identifiers if identifier in by_id]


def search(path, question, limit=5):
    """Use quoted lexical terms; unfamiliar requests do not match on 'Newark' alone."""
    if not isinstance(question, str) or not Path(path).exists():
        return []
    words = list(dict.fromkeys(re.findall(r"[\w]+", question.lower(), re.UNICODE)))
    terms = [word for word in words if word not in STOP_WORDS][:16]
    if not terms:
        terms = [word.rstrip("s") for word in words if word in GENERIC_RECORD_WORDS]
    if not terms:
        return []
    query = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
    limit = max(1, min(int(limit), MAX_RESULTS))
    with _connection(path) as connection:
        rows = connection.execute(
            _CHUNK_SELECT + " JOIN civic_fts AS f ON f.chunk_id=c.chunk_id "
            "WHERE civic_fts MATCH ? "
            "ORDER BY bm25(civic_fts), "
            "json_extract(s.metadata, '$.meeting_date') DESC, c.chunk_id LIMIT ?",
            (query, limit),
        ).fetchall()
    return [_chunk_row(row, index + 1) for index, row in enumerate(rows)]


def snapshot(path, limit=5):
    """Describe an explicit import snapshot; it is not a live city-wide feed."""
    empty = {"sources": 0, "chunks": 0, "last_fetched_at": None, "documents": []}
    if not Path(path).exists():
        return empty
    limit = max(1, min(int(limit), MAX_BATCH_DOCUMENTS))
    with _connection(path) as connection:
        counts = connection.execute(
            "SELECT COUNT(*) AS sources, MAX(fetched_at) AS last_fetched_at "
            "FROM civic_sources"
        ).fetchone()
        chunk_count = connection.execute(
            "SELECT COUNT(*) FROM civic_chunks"
        ).fetchone()[0]
        documents = []
        for row in connection.execute(
            "SELECT * FROM civic_sources ORDER BY "
            "json_extract(metadata, '$.meeting_date') DESC, "
            "json_extract(metadata, '$.kind') DESC, source_id LIMIT ?",
            (limit,),
        ):
            document = dict(row)
            document["metadata"] = json.loads(document["metadata"])
            documents.append(document)
    return {
        "sources": counts["sources"],
        "chunks": chunk_count,
        "last_fetched_at": counts["last_fetched_at"],
        "documents": documents,
    }
