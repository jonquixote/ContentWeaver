"""project.transcript

Revision ID: b7e1d2c3a4f5
Revises: a3f1c9d24e07
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e1d2c3a4f5'
down_revision: Union[str, Sequence[str], None] = 'a3f1c9d24e07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable word-level transcript JSON ({word,start,end} list) captured
    # after TTS; consumed by YouTube caption upload and viral re-detection.
    op.add_column('project', sa.Column('transcript', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('project', 'transcript')
