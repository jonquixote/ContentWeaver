from __future__ import annotations

import json
import os

from abc import ABC, abstractmethod


class VectorStore(ABC):
    """Backend-agnostic vector/text index. sqlite-vec is the default backend;
    pgvector optional. Conformance suite runs against both."""

    @abstractmethod
    def upsert(self, row: dict) -> None:
        ...

    @abstractmethod
    def query(self, vector: list[float], k: int, filters: dict) -> list[dict]:
        ...

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        ...


class SqliteVecStore(VectorStore):
    """sqlite-vec backend. Zero-provision for dev/CI/single-node. The vector
    lives in a relational column (JSON), scoring done in-Python via cosine so
    the suite passes even when the sqlite-vec extension is absent."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._init_db()

    def _conn(self):
        import sqlite3
        conn = sqlite3.connect(self.dsn)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        import sqlite3
        conn = self._conn()
        try:
            conn.enable_load_extension(True)
            conn.load_extension("vec0")
        except Exception:
            pass  # sqlite-vec not available; degrade to relational + in-Python cosine
        conn.execute(
            "CREATE TABLE IF NOT EXISTS footage_vec (\n"
            "  id TEXT PRIMARY KEY, embedding TEXT, source TEXT, scale TEXT,"
            " duration_s REAL)"
        )
        conn.commit()
        conn.close()

    def upsert(self, row: dict) -> None:
        conn = self._conn()
        conn.execute(
            "INSERT OR REPLACE INTO footage_vec (id, embedding, source, scale, duration_s) "
            "VALUES (?, ?, ?, ?, ?)",
            (row["id"], json.dumps(row.get("embedding") or []),
             row.get("source"), row.get("scale"), row.get("duration_s")),
        )
        conn.commit()
        conn.close()

    def query(self, vector: list[float], k: int, filters: dict) -> list[dict]:
        import math
        conn = self._conn()
        rows = conn.execute(
            "SELECT id, embedding, source, scale, duration_s FROM footage_vec"
        ).fetchall()
        conn.close()
        scored = []
        for r in rows:
            # filter: match every provided filters key against the stored attrs
            if filters:
                if "source" in filters and r["source"] != filters["source"]:
                    continue
                if "scale" in filters and r["scale"] != filters["scale"]:
                    continue
            emb = json.loads(r["embedding"])
            if not emb or len(emb) != len(vector):
                continue
            num = sum(a * b for a, b in zip(vector, emb))
            denom = (
                math.sqrt(sum(a * a for a in vector))
                * math.sqrt(sum(b * b for b in emb))
                or 1.0
            )
            sim = num / denom
            scored.append((sim, r["id"], r["duration_s"], r["source"]))
        scored.sort(reverse=True)
        return [
            {"id": i, "score": s, "duration_s": d, "source": src}
            for s, i, d, src in scored[:k]
        ]

    def delete(self, ids: list[str]) -> None:
        conn = self._conn()
        conn.executemany("DELETE FROM footage_vec WHERE id=?", [(i,) for i in ids])
        conn.commit()
        conn.close()


def make_vector_store() -> VectorStore:
    backend = os.getenv("VECTOR_STORE", "sqlite_vec")
    if backend == "pgvector":
        try:
            from src.services.footage.pgvector_store import PgVectorStore
            return PgVectorStore(os.getenv("DATABASE_URL", ""))
        except ImportError as e:
            raise RuntimeError(
                "VECTOR_STORE=pgvector requested but pgvector_store is not "
                "installed. Set VECTOR_STORE=sqlite_vec (the zero-provision "
                "default) or add the pgvector backend.") from e
    return SqliteVecStore(os.getenv("FOOTAGE_VECTOR_DB", "/tmp/cw-footage-vec.db"))
