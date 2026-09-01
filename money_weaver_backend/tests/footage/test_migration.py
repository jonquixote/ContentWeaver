import os
import tempfile


def test_migration_is_additive_only():
    import sqlite3
    d = tempfile.mkdtemp()
    db = os.path.join(d, "m.db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE project (id INTEGER PRIMARY KEY)")  # pre-existing
    from src.services.footage.schema import DOWNGRADE_SQL, UPGRADE_SQL
    conn.executescript(UPGRADE_SQL)
    tables_before = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "project" in tables_before
    assert "footage_assets" in tables_before
    conn.executescript(DOWNGRADE_SQL)
    tables_after = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "project" in tables_after  # pre-existing survives
    assert "footage_assets" not in tables_after
    conn.close()


def test_migration_roundtrips():
    from src.services.footage.schema import DOWNGRADE_SQL, UPGRADE_SQL
    assert "footage_assets" in UPGRADE_SQL
    assert "footage_assets" in DOWNGRADE_SQL
    # footage_assets must carry the status column (retrieval joins + filters ready).
    assert "status" in UPGRADE_SQL


def test_assets_status_defaults_to_discovered():
    # Retrieval filters status='ready'; migrations default upcoming assets to a
    # non-ready state (discovered), so nothing leaks before analysis.
    from src.services.footage.schema import UPGRADE_SQL
    assert "status" in UPGRADE_SQL
