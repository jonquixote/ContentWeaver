"""add generation_type to task

Revision ID: xxxxx_task_generation_type
Revises: 71ef82baf855
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'xxxxx_task_generation_type'
down_revision: Union[str, Sequence[str], None] = '71ef82baf855'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('task', sa.Column('generation_type', sa.String(20), server_default='assembler', nullable=False))


def downgrade() -> None:
    op.drop_column('task', 'generation_type')