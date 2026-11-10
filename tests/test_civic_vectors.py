"""Actual SQLite extension checks using numeric fixtures, not semantic AI claims."""

import sqlite3

import pytest

import civic_embed
from app import civic_store, civic_vectors


def _document(identifier="fixture-budget", text="Budget hearing at City Hall."):
    return {
        "source_id": identifier,
        "title": "Fixture " + identifier,
        "url": "https://newark.legistar.com/MeetingDetail.aspx?ID=123",
        "heading": "Fixture public record",
        "text": text,
        "fetched_at": "2026-11-10T12:00:00+00:00",
        "source_updated_at": "2026-11-09T12:00:00+00:00",
        "metadata": {"fixture": True},
    }


@pytest.fixture
def database(tmp_path):
    """Every test gets public synthetic records and an isolated database."""
    path = tmp_path / "civic.sqlite3"
    civic_store.upsert_documents(
        path,
        [
            _document(),
            _document("fixture-transport", "Bus transport consultation at City Hall."),
        ],
    )
    return path


def _fixture_embeddings(texts):
    """Known vectors test ranking mechanics only, not a real embedding model."""
    return [[1.0, 0.0, 0.0] if "Budget" in text else [0.0, 1.0, 0.0] for text in texts]


def _index(path, embedder=_fixture_embeddings, model="fixture-model"):
    return civic_vectors.index_chunks(path, embedder, model, dimensions=3)


def test_actual_vec_extension_ranks_current_records(database):
    result = _index(database)
    assert result["indexed"] == 2
    rows = civic_vectors.search_vectors(database, [1.0, 0.0, 0.0], "fixture-model")
    assert rows[0]["source_id"] == "fixture-budget"
    assert rows[0]["vector_distance"] == pytest.approx(0.0)
    assert rows[0]["metadata"] == {"fixture": True}
    assert rows[0]["url"].startswith("https://newark.legistar.com/")
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'civic_vectors'"
            )
            .fetchone()[0]
            .startswith("CREATE VIRTUAL TABLE")
        )


def test_unchanged_import_does_not_repeat_embedding_calls(database):
    _index(database)
    civic_store.upsert_documents(database, [_document()])

    def unexpected_call(_texts):
        pytest.fail("Unchanged chunks must not cause another provider request")

    result = _index(database, unexpected_call)
    assert result["indexed"] == 0
    assert result["unchanged"] == 2
    status = civic_vectors.index_status(database, "fixture-model")
    assert status["complete"] is True
    assert status["indexed_chunks"] == status["total_chunks"] == 2


def test_source_changes_never_return_stale_vector_evidence(database):
    _index(database)
    old = civic_vectors.search_vectors(database, [1, 0, 0], "fixture-model")[0]
    civic_store.upsert_documents(database, [_document(text="Budget session moved.")])
    rows = civic_vectors.search_vectors(database, [1, 0, 0], "fixture-model")
    assert old["chunk_id"] not in {row["chunk_id"] for row in rows}
    assert "fixture-budget" not in {row["source_id"] for row in rows}
    status = civic_vectors.index_status(database)
    assert status["indexed_chunks"] == 1 and status["complete"] is False
    result = _index(database)
    assert result["indexed"] == 1 and result["unchanged"] == 1
    rows = civic_vectors.search_vectors(database, [1, 0, 0], "fixture-model")
    assert rows[0]["text"] == "Budget session moved."
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM civic_vector_chunks").fetchone()[0]
            == 2
        )


def test_changed_during_provider_call_is_skipped(database):
    def change_source(texts):
        civic_store.upsert_documents(
            database, [_document(text="Budget changed meanwhile.")]
        )
        return _fixture_embeddings(texts)

    result = _index(database, change_source)
    assert result["skipped_stale"] == 1
    rows = civic_vectors.search_vectors(database, [1, 0, 0], "fixture-model")
    assert all(row["source_id"] != "fixture-budget" for row in rows)


def test_replacing_every_source_cleans_orphan_vectors_before_insert(database):
    _index(database)
    civic_store.upsert_documents(
        database,
        [
            _document(text="Budget record replaced."),
            _document("fixture-transport", "Transport record replaced."),
        ],
    )
    assert civic_vectors.search_vectors(database, [1, 0, 0], "fixture-model") == []
    result = _index(database)
    assert result["indexed"] == 2
    assert civic_vectors.index_status(database)["complete"] is True
    rows = civic_vectors.search_vectors(database, [1, 0, 0], "fixture-model")
    assert {row["text"] for row in rows} == {
        "Budget record replaced.",
        "Transport record replaced.",
    }


def test_provider_failure_preserves_previous_model_index(database):
    _index(database)

    def fail(_texts):
        raise RuntimeError("Fixture upstream failure")

    with pytest.raises(RuntimeError, match="Fixture upstream failure"):
        _index(database, fail, "replacement-fixture-model")
    assert civic_vectors.index_status(database)["model"] == "fixture-model"
    assert civic_vectors.search_vectors(database, [1, 0, 0], "fixture-model")


@pytest.mark.parametrize(
    "vector",
    [
        [1.0, float("nan"), 0.0],
        [1.0, float("inf"), 0.0],
        [1.0, True, 0.0],
        [1.0, 1e50, 0.0],
        [0.0, 0.0, 0.0],
        [1e-300, 0.0, 0.0],
        [1.0, 0.0],
    ],
)
def test_invalid_model_vectors_do_not_create_an_index(database, vector):
    with pytest.raises(ValueError):
        _index(database, lambda texts: [vector for _ in texts])
    assert civic_vectors.index_status(database)["indexed_chunks"] == 0
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'civic_vectors'"
            ).fetchone()
            is None
        )


def test_wrong_embedding_batch_is_rejected(database):
    with pytest.raises(ValueError, match="wrong batch size"):
        _index(database, lambda _texts: [])


def test_model_and_dimension_mismatches_cannot_mix_vectors(database):
    _index(database)
    assert civic_vectors.search_vectors(database, [1, 0, 0], "other-model") == []
    assert civic_vectors.index_status(database, "other-model")["compatible"] is False
    assert civic_vectors.index_status(database, "other-model")["indexed_chunks"] == 0
    with pytest.raises(ValueError, match="dimensions"):
        civic_vectors.search_vectors(database, [1, 0], "fixture-model")


def test_missing_database_reads_do_not_create_files(tmp_path):
    path = tmp_path / "absent.sqlite3"
    assert civic_vectors.search_vectors(path, [1, 0, 0], "fixture-model") == []
    assert civic_vectors.index_status(path)["indexed_chunks"] == 0
    assert not path.exists()


def test_missing_extension_has_actionable_status(database, monkeypatch):
    def missing(_connection):
        raise civic_vectors.VectorIndexUnavailable("Fixture package missing")

    monkeypatch.setattr(civic_vectors, "_load_extension", missing)
    assert civic_vectors.index_status(database)["available"] is False
    with pytest.raises(civic_vectors.VectorIndexUnavailable):
        _index(database)


def test_corpus_limit_is_checked_before_provider_calls(database, monkeypatch):
    monkeypatch.setattr(civic_store, "list_chunks", lambda _path: [{}] * 101)
    with pytest.raises(ValueError, match="100 public chunks"):
        _index(database, lambda _texts: pytest.fail("Provider must not be called"))


def test_model_replacement_changes_the_index_atomically(database):
    _index(database)
    result = civic_vectors.index_chunks(
        database,
        lambda texts: [[1.0, 0.0] for _ in texts],
        "two-dimension-fixture",
        dimensions=2,
    )
    assert result["indexed"] == 2
    status = civic_vectors.index_status(database)
    assert status["model"] == "two-dimension-fixture" and status["dimensions"] == 2
    assert civic_vectors.search_vectors(database, [1, 0, 0], "fixture-model") == []
    assert civic_vectors.search_vectors(database, [1, 0], "two-dimension-fixture")


def test_cli_refuses_api_usage_without_explicit_flag(monkeypatch):
    monkeypatch.setattr(
        civic_embed.civic_ai,
        "configuration_status",
        lambda: pytest.fail("Do not even inspect model configuration before consent"),
    )
    with pytest.raises(SystemExit) as error:
        civic_embed.main([])
    assert error.value.code == 2


def test_cli_refuses_unconfigured_key(monkeypatch):
    monkeypatch.setattr(
        civic_embed.civic_ai, "configuration_status", lambda: {"configured": False}
    )
    with pytest.raises(SystemExit) as error:
        civic_embed.main(["--confirm-api-usage"])
    assert error.value.code == 2
