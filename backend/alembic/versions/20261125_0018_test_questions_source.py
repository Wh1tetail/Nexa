"""Book-to-Test, stage 7: where a library question came from (book, pages, quote).

One nullable JSONB column; existing rows stay NULL, no table rewrite.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-25 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0018'
down_revision: Union[str, None] = '0017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('test_questions', sa.Column('source', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('test_questions', 'source')
