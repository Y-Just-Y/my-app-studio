"""Optional sqlite-vec index bound to the current public civic source versions.

Only the explicit embedding CLI writes this index. A missing key/index must not
turn keyword matches or numeric test fixtures into claimed semantic retrieval.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
from pathlib import Path
import sqlite3
import struct

from app import civic_store

MAX_CHUNKS = 100
DEFAULT_DIMENSIONS = 1536
MAX_DIMENSIONS = 4096
FLOAT32_MAX = 3.4028234663852886e38


class VectorIndexUnavailable(RuntimeError):
    """The optional package/runtime cannot supply an actual vector index."""


def _load_extension(connection):
    """Load only the installed package, then close extension loading again."""
    try:
        module = importlib.import_module("sqlite_vec")
        connection.enable_load_extension(True)
        try:
            module.load(connection)
        finally:
            connection.enable_load_extension(False)
        return module
    except (ImportError, AttributeError, OSError, sqlite3.Error):
        raise VectorIndexUnavailable(
            "sqlite-vec is unavailable in this Python environment. "
            "Keyword search remains available."
        ) from None


@contextmanager
def _connection(path, *, write=False):
    """Never create a database or mutate one from a web search/status call."""
    database = Path(path).resolve()
    mode = "rw" if write else "ro"
    connection = sqlite3.connect(
        database.as_uri() + f"?mode={mode}", uri=True, timeout=5
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        _load_extension(connection)
        yield connection
        if write:
            connection.commit()
    except BaseException:
        if write:
            connection.rollback()
        raise
    finally:
        connection.close()


def _validate_configuration(model, dimensions, batch_size):
    if not isinstance(model, str) or not model.strip() or len(model) > 128:
        raise ValueError("Choose a nonempty embedding model name.")
    if "\n" in model or "\r" in model:
        raise ValueError("Choose a single embedding model name.")
    if (
        isinstance(dimensions, bool)
        or not isinstance(dimensions, int)
        or not 1 <= dimensions <= MAX_DIMENSIONS
    ):
        raise ValueError("Embedding dimensions must be between 1 and 4096.")
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or not 1 <= batch_size <= 32
    ):
        raise ValueError("Embedding batches must contain between 1 and 32 chunks.")


def _validated_vector(vector, dimensions):
    if not isinstance(vector, (list, tuple)) or len(vector) != dimensions:
        raise ValueError("The embedding does not match the index dimensions.")
    values = []
    for value in vector:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or abs(value) > FLOAT32_MAX
        ):
            raise ValueError("Embeddings must contain finite float32 numbers.")
        values.append(float(value))
    values = list(
        struct.unpack(f"{dimensions}f", struct.pack(f"{dimensions}f", *values))
    )
    if not any(values):
        raise ValueError("A zero embedding cannot be used for cosine search.")
    return values


def _embedding_text(chunk):
    return f"{chunk['title']}\n{chunk['heading']}\n{chunk['text']}"


def _input_hash(chunk):
    return hashlib.sha256(_embedding_text(chunk).encode("utf-8")).hexdigest()


def _configuration(connection):
    present = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'civic_vector_config'"
    ).fetchone()
    if not present:
        return None
    row = connection.execute(
        "SELECT model, dimensions FROM civic_vector_config WHERE id = 1"
    ).fetchone()
    return dict(row) if row else None


def _current_rows(connection):
    return connection.execute(
        """SELECT c.chunk_id, c.source_id, c.heading, c.text, c.content_hash,
                  c.version, s.title, s.url, s.fetched_at, s.source_updated_at,
                  s.metadata, s.content_hash AS source_hash
           FROM civic_chunks c JOIN civic_sources s ON s.source_id = c.source_id
           WHERE c.version = s.version ORDER BY c.chunk_id"""
    ).fetchall()


def _create_index(connection, model, dimensions):
    current = _configuration(connection)
    if current and current == {"model": model, "dimensions": dimensions}:
        return
    # The replacement happens in the same transaction as the complete new batch.
    connection.execute("DROP TABLE IF EXISTS civic_vectors")
    connection.execute("DROP TABLE IF EXISTS civic_vector_chunks")
    connection.execute("""CREATE TABLE IF NOT EXISTS civic_vector_config (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            model TEXT NOT NULL, dimensions INTEGER NOT NULL
        )""")
    connection.execute("""CREATE TABLE civic_vector_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_id TEXT NOT NULL UNIQUE
                REFERENCES civic_chunks(chunk_id) ON DELETE CASCADE,
            content_hash TEXT NOT NULL, input_hash TEXT NOT NULL,
            model TEXT NOT NULL, indexed_at TEXT NOT NULL
        )""")
    # The dimension is a range-checked integer, never user-supplied SQL syntax.
    connection.execute(
        "CREATE VIRTUAL TABLE civic_vectors USING vec0("
        f"id INTEGER PRIMARY KEY, embedding float[{dimensions}] "
        "distance_metric=cosine)"
    )
    connection.execute(
        "INSERT OR REPLACE INTO civic_vector_config VALUES (1, ?, ?)",
        (model, dimensions),
    )


def _existing_rows(connection, model, dimensions):
    if _configuration(connection) != {"model": model, "dimensions": dimensions}:
        return {}
    return {
        row["chunk_id"]: dict(row)
        for row in connection.execute("SELECT * FROM civic_vector_chunks")
    }


def _remove_stale(connection):
    connection.execute("""DELETE FROM civic_vector_chunks WHERE NOT EXISTS (
            SELECT 1 FROM civic_chunks c JOIN civic_sources s
                ON s.source_id = c.source_id
            WHERE c.chunk_id = civic_vector_chunks.chunk_id
                AND c.content_hash = civic_vector_chunks.content_hash
                AND c.version = s.version)""")
    valid = {
        row["id"] for row in connection.execute("SELECT id FROM civic_vector_chunks")
    }
    for row in connection.execute("SELECT id FROM civic_vectors").fetchall():
        if row["id"] not in valid:
            connection.execute("DELETE FROM civic_vectors WHERE id = ?", (row["id"],))


def _collect_embeddings(pending, embedder, dimensions, batch_size):
    prepared = {}
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset : offset + batch_size]
        vectors = embedder([_embedding_text(chunk) for chunk in batch])
        if not isinstance(vectors, list) or len(vectors) != len(batch):
            raise ValueError("The embedding service returned the wrong batch size.")
        for chunk, vector in zip(batch, vectors, strict=True):
            prepared[chunk["chunk_id"]] = _validated_vector(vector, dimensions)
    return prepared


def _write_embeddings(connection, pending, prepared, model, dimensions):
    module = _load_extension(connection)
    _create_index(connection, model, dimensions)
    _remove_stale(connection)
    current = {row["chunk_id"]: dict(row) for row in _current_rows(connection)}
    indexed = skipped = 0
    timestamp = datetime.now(timezone.utc).isoformat()
    for chunk in pending:
        latest = current.get(chunk["chunk_id"])
        if latest is None or _input_hash(latest) != _input_hash(chunk):
            skipped += 1
            continue
        old = connection.execute(
            "SELECT id FROM civic_vector_chunks WHERE chunk_id = ?",
            (chunk["chunk_id"],),
        ).fetchone()
        if old:
            connection.execute("DELETE FROM civic_vectors WHERE id = ?", (old["id"],))
            connection.execute(
                "DELETE FROM civic_vector_chunks WHERE id = ?", (old["id"],)
            )
        cursor = connection.execute(
            """INSERT INTO civic_vector_chunks
               (chunk_id, content_hash, input_hash, model, indexed_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                chunk["chunk_id"],
                chunk["content_hash"],
                _input_hash(chunk),
                model,
                timestamp,
            ),
        )
        connection.execute(
            "INSERT INTO civic_vectors(id, embedding) VALUES (?, ?)",
            (
                cursor.lastrowid,
                module.serialize_float32(prepared[chunk["chunk_id"]]),
            ),
        )
        indexed += 1
    _remove_stale(connection)
    return indexed, skipped


def index_chunks(
    path, embedder, model, *, dimensions=DEFAULT_DIMENSIONS, batch_size=16
):
    """Embed only changed public chunks after an explicit admin CLI action.

    All model calls finish before the SQLite write transaction starts. Failed
    batches leave the previous index intact; changed-during-call chunks are not
    attached to an outdated vector.
    """
    _validate_configuration(model, dimensions, batch_size)
    if not Path(path).is_file():
        raise ValueError("Import public civic sources before embedding them.")
    chunks = civic_store.list_chunks(path)
    if len(chunks) > MAX_CHUNKS:
        raise ValueError("This classroom index is limited to 100 public chunks.")
    with _connection(path) as connection:
        existing = _existing_rows(connection, model, dimensions)
    pending = [
        chunk
        for chunk in chunks
        if chunk["chunk_id"] not in existing
        or existing[chunk["chunk_id"]]["input_hash"] != _input_hash(chunk)
        or existing[chunk["chunk_id"]]["content_hash"] != chunk["content_hash"]
    ]
    prepared = _collect_embeddings(pending, embedder, dimensions, batch_size)
    with _connection(path, write=True) as connection:
        connection.execute("BEGIN IMMEDIATE")
        indexed, skipped = _write_embeddings(
            connection, pending, prepared, model, dimensions
        )
    return {
        "indexed": indexed,
        "unchanged": len(chunks) - len(pending),
        "skipped_stale": skipped,
        "total_chunks": len(chunks),
        "model": model,
        "dimensions": dimensions,
    }


def _status_empty(*, available=False):
    return {
        "available": available,
        "indexed_chunks": 0,
        "total_chunks": 0,
        "model": None,
        "dimensions": None,
        "complete": False,
        "compatible": True,
    }


def index_status(path, model=None):
    """Report actual compatible indexed rows, never requiring an API key."""
    if not Path(path).is_file():
        return _status_empty()
    try:
        with _connection(path) as connection:
            total = connection.execute("SELECT COUNT(*) FROM civic_chunks").fetchone()[
                0
            ]
            current = _configuration(connection)
            if not current:
                return {**_status_empty(available=True), "total_chunks": total}
            compatible = model is None or current["model"] == model
            count = connection.execute(
                """SELECT COUNT(*) FROM civic_vector_chunks m
                   JOIN civic_chunks c ON c.chunk_id = m.chunk_id
                       AND c.content_hash = m.content_hash
                   JOIN civic_sources s ON s.source_id = c.source_id
                   WHERE c.version = s.version AND m.model = ?""",
                (current["model"],),
            ).fetchone()[0]
            return {
                "available": True,
                "indexed_chunks": count if compatible else 0,
                "total_chunks": total,
                **current,
                "complete": compatible and 0 < total == count,
                "compatible": compatible,
            }
    except (sqlite3.Error, VectorIndexUnavailable):
        return _status_empty()


def _search_results(connection, distances, model, limit):
    results = []
    for chunk in _current_rows(connection):
        mapping = connection.execute(
            "SELECT * FROM civic_vector_chunks WHERE chunk_id = ? AND model = ?",
            (chunk["chunk_id"], model),
        ).fetchone()
        if (
            mapping is None
            or mapping["id"] not in distances
            or mapping["content_hash"] != chunk["content_hash"]
            or mapping["input_hash"] != _input_hash(chunk)
        ):
            continue
        row = dict(chunk)
        row["metadata"] = json.loads(row["metadata"])
        row["vector_distance"] = distances[mapping["id"]]
        row["score"] = 1.0 - row["vector_distance"]
        results.append(row)
    return sorted(results, key=lambda row: row["vector_distance"])[:limit]


def search_vectors(path, vector, model, limit=5):
    """Search actual vectors and current records using a read-only connection."""
    if not Path(path).is_file():
        return []
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
        raise ValueError("Choose between 1 and 10 retrieved chunks.")
    with _connection(path) as connection:
        configuration = _configuration(connection)
        if not configuration or configuration["model"] != model:
            return []
        values = _validated_vector(vector, configuration["dimensions"])
        module = _load_extension(connection)
        # The entire local corpus is capped at 100 chunks. Retrieving those rows
        # before the current-version join keeps deleted vectors from hiding valid
        # candidates after an import but before the next explicit index command.
        matches = connection.execute(
            """SELECT id, distance FROM civic_vectors
               WHERE embedding MATCH ? AND k = ? ORDER BY distance""",
            (module.serialize_float32(values), MAX_CHUNKS),
        ).fetchall()
        distances = {row["id"]: row["distance"] for row in matches}
        return _search_results(connection, distances, model, limit)
