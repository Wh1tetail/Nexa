"""test settings and files

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-15 00:28:06.974964
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('attachments', sa.Column('test_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_attachments_test_id'), 'attachments', ['test_id'], unique=False)
    op.create_foreign_key(op.f('fk_attachments_test_id_tests'), 'attachments', 'tests', ['test_id'], ['id'], ondelete='CASCADE')
    op.add_column('test_questions', sa.Column('explanation', sa.Text(), nullable=True))
    op.add_column('test_questions', sa.Column('attachment_ids', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.add_column('tests', sa.Column('available_from', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tests', sa.Column('shuffle_questions', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('tests', sa.Column('shuffle_options', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('tests', sa.Column('show_correct_answers', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('tests', sa.Column('passing_percent', sa.Integer(), nullable=True))

    op.create_check_constraint(
        op.f('ck_tests_passing_percent_range'), 'tests',
        'passing_percent IS NULL OR passing_percent BETWEEN 1 AND 100',
    )
    # attachments get a fourth possible owner: a test (its materials)
    op.drop_constraint(op.f('ck_attachments_single_owner'), 'attachments', type_='check')
    op.create_check_constraint(
        op.f('ck_attachments_single_owner'), 'attachments',
        '(homework_id IS NOT NULL)::int + (submission_id IS NOT NULL)::int + (message_id IS NOT NULL)::int + (test_id IS NOT NULL)::int = 1',
    )


def downgrade() -> None:
    # test materials cannot exist under the old constraint (stored objects stay in storage)
    op.execute('DELETE FROM attachments WHERE test_id IS NOT NULL')
    op.drop_constraint(op.f('ck_attachments_single_owner'), 'attachments', type_='check')
    op.create_check_constraint(
        op.f('ck_attachments_single_owner'), 'attachments',
        '(homework_id IS NOT NULL)::int + (submission_id IS NOT NULL)::int + (message_id IS NOT NULL)::int = 1',
    )
    op.drop_constraint(op.f('ck_tests_passing_percent_range'), 'tests', type_='check')
    op.drop_column('tests', 'passing_percent')
    op.drop_column('tests', 'show_correct_answers')
    op.drop_column('tests', 'shuffle_options')
    op.drop_column('tests', 'shuffle_questions')
    op.drop_column('tests', 'available_from')
    op.drop_column('test_questions', 'attachment_ids')
    op.drop_column('test_questions', 'explanation')
    op.drop_constraint(op.f('fk_attachments_test_id_tests'), 'attachments', type_='foreignkey')
    op.drop_index(op.f('ix_attachments_test_id'), table_name='attachments')
    op.drop_column('attachments', 'test_id')
