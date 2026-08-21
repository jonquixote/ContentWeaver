"""voices.voice_engine

Revision ID: a3f1c9d24e07
Revises: xxxxx_task_generation_type
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c9d24e07'
down_revision: Union[str, Sequence[str], None] = 'xxxxx_task_generation_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default backfills existing rows with 'moss' (the pre-engine
    # default), matching the model's Python-side default.
    op.add_column('voices', sa.Column(
        'voice_engine', sa.String(20), server_default='moss', nullable=False))


def downgrade() -> None:
    op.drop_column('voices', 'voice_engine')
