from __future__ import annotations

# SQL source of truth for the footage relational tables. Alembic migration
# 0001_footage wraps these; the additive-only contract (never touches
# pre-existing tables) is asserted by tests/footage/test_migration.py.

UPGRADE_SQL = """
CREATE TABLE IF NOT EXISTS footage_assets (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    title TEXT,
    description TEXT,
    tags TEXT DEFAULT '[]',
    subjects TEXT DEFAULT '[]',
    creator TEXT,
    published_at TEXT,
    duration_s REAL,
    width INTEGER,
    height INTEGER,
    aspect TEXT,
    license_spdx TEXT NOT NULL,
    license_raw TEXT,
    attribution_required INTEGER DEFAULT 0,
    attribution_text TEXT,
    page_url TEXT NOT NULL,
    download_url TEXT,
    storage_prefix TEXT,
    status TEXT DEFAULT 'discovered',
    source_metadata TEXT DEFAULT '{}',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS footage_shots (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    shot_idx INTEGER NOT NULL,
    start_s REAL NOT NULL,
    end_s REAL NOT NULL,
    keyframe_path TEXT,
    embedding TEXT,
    caption TEXT,
    shot_scale TEXT,
    camera_move TEXT,
    motion_energy REAL,
    faces_count INTEGER DEFAULT 0,
    has_text_overlay INTEGER DEFAULT 0,
    brightness REAL,
    color_palette TEXT
);
CREATE TABLE IF NOT EXISTS ingest_jobs (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    query TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    discovered INTEGER DEFAULT 0,
    filtered_out INTEGER DEFAULT 0,
    ingested INTEGER DEFAULT 0,
    error TEXT,
    created_at TEXT,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS ingest_rejections (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    detail TEXT DEFAULT '{}',
    created_at TEXT
);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS ingest_rejections;
DROP TABLE IF EXISTS ingest_jobs;
DROP TABLE IF EXISTS footage_shots;
DROP TABLE IF EXISTS footage_assets;
"""
