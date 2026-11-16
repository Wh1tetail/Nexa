"""test task types

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-16 22:51:19.195591
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('test_attempts', sa.Column('plays', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))
    op.add_column('test_questions', sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))
    # new question types: gaps, matching, and content blocks (audio, reading) worth 0 points
    op.drop_constraint(op.f('ck_test_questions_question_type'), 'test_questions', type_='check')
    op.create_check_constraint(op.f('ck_test_questions_question_type'), 'test_questions', "type IN ('single_choice', 'multiple_choice', 'true_false', 'short_answer', 'fill_gaps', 'matching', 'audio', 'reading')")
    op.drop_constraint(op.f('ck_test_questions_points_positive'), 'test_questions', type_='check')
    op.create_check_constraint(op.f('ck_test_questions_points_not_negative'), 'test_questions', 'points >= 0')


def downgrade() -> None:
    # questions of the new types cannot exist in the old schema (their answers go with them)
    op.execute("DELETE FROM test_questions WHERE type IN ('fill_gaps', 'matching', 'audio', 'reading')")
    op.drop_constraint(op.f('ck_test_questions_points_not_negative'), 'test_questions', type_='check')
    op.create_check_constraint(op.f('ck_test_questions_points_positive'), 'test_questions', 'points > 0')
    op.drop_constraint(op.f('ck_test_questions_question_type'), 'test_questions', type_='check')
    op.create_check_constraint(op.f('ck_test_questions_question_type'), 'test_questions', "type IN ('single_choice', 'multiple_choice', 'true_false', 'short_answer')")
    op.drop_column('test_questions', 'config')
    op.drop_column('test_attempts', 'plays')
