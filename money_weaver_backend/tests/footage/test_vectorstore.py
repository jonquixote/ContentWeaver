import os
import tempfile

from src.services.footage.vectorstore import SqliteVecStore, VectorStore


def _store():
    d = tempfile.mkdtemp(prefix="footage-vs-")
    return SqliteVecStore(os.path.join(d, "vec.db"))


def test_sqlite_vec_upsert_and_query_returns_nearest():
    s = _store()
    s.upsert({"id": "a", "embedding": [1.0, 0.0, 0.0], "source": "pexels", "scale": "ms"})
    s.upsert({"id": "b", "embedding": [0.0, 1.0, 0.0], "source": "pixabay", "scale": "cu"})
    res = s.query([1.0, 0.0, 0.0], k=2, filters={})
    assert res[0]["id"] == "a"  # nearest to query vector
    assert len(res) == 2


def test_sqlite_vec_query_applies_filters():
    s = _store()
    s.upsert({"id": "a", "embedding": [1.0, 0.0], "source": "pexels"})
    s.upsert({"id": "b", "embedding": [1.0, 0.0], "source": "pixabay"})
    res = s.query([1.0, 0.0], k=5, filters={"source": "pexels"})
    assert [r["id"] for r in res] == ["a"]


def test_sqlite_vec_delete():
    s = _store()
    s.upsert({"id": "a", "embedding": [1.0, 0.0]})
    s.delete(["a"])
    assert s.query([1.0, 0.0], k=5, filters={}) == []


def test_vectorstore_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        VectorStore()  # ABC: cannot instantiate


def test_make_vector_store_pgvector_missing_raises_actionable(monkeypatch):
    import pytest
    from src.services.footage.vectorstore import make_vector_store
    monkeypatch.setenv("VECTOR_STORE", "pgvector")
    with pytest.raises(RuntimeError) as ei:
        make_vector_store()
    assert "VECTOR_STORE=sqlite_vec" in str(ei.value)  # actionable guidance


def test_make_vector_store_defaults_to_sqlite(monkeypatch):
    from src.services.footage.vectorstore import SqliteVecStore, make_vector_store
    monkeypatch.delenv("VECTOR_STORE", raising=False)
    assert isinstance(make_vector_store(), SqliteVecStore)
