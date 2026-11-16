"""soft removal of participants and assignees

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-16 22:28:54.002730
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL = active; existing rows stay active
    op.add_column('attendance', sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('homework_submissions', sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('test_assignments', sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # rows taken off lessons / tests / homework become active again (no data is deleted)
    op.drop_column('test_assignments', 'removed_at')
    op.drop_column('homework_submissions', 'removed_at')
    op.drop_column('attendance', 'removed_at')
