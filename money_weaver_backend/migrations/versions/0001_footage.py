"""footage tables (additive-only)

Revision ID: 0001_footage
Revises: c8f2e3d4a5b6
Create Date: 2026-09-01
"""
from alembic import op
import sqlalchemy as sa  # noqa: F401

from src.services.footage.schema import DOWNGRADE_STATEMENTS, UPGRADE_STATEMENTS

revision = "0001_footage"
down_revision = "c8f2e3d4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Additive-only footage DDL: creates footage_assets, footage_shots,
    # ingest_jobs, ingest_rejections. Never drops/alters any pre-existing table.
    # Iterate statements: sqlite via SQLAlchemy is "one statement at a time".
    for stmt in UPGRADE_STATEMENTS:
        op.execute(sa.text(stmt))


def downgrade() -> None:
    # Drops ONLY the four footage_* tables; pre-existing tables untouched.
    for stmt in DOWNGRADE_STATEMENTS:
        op.execute(sa.text(stmt))
