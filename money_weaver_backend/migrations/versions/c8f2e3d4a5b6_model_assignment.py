"""add model_assignment table

Revision ID: c8f2e3d4a5b6
Revises: b7e1d2c3a4f5
Create Date: 2026-08-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c8f2e3d4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b7e1d2c3a4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'model_assignment',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('task', sa.String(length=32), nullable=False),
        sa.Column('model_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'task', name='uq_model_assignment_user_task'),
    )


def downgrade() -> None:
    op.drop_table('model_assignment')
