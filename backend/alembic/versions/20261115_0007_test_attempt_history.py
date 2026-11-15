"""test attempt history

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-15 19:50:12.970301
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('test_assignments', sa.Column('extra_attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('test_attempts', sa.Column('number', sa.Integer(), server_default='1', nullable=False))
    op.drop_constraint(op.f('uq_attempt_test_student'), 'test_attempts', type_='unique')
    op.create_index('uq_attempt_one_in_progress', 'test_attempts', ['test_id', 'student_id'], unique=True, postgresql_where=sa.text("status = 'in_progress'"))
    op.create_unique_constraint(op.f('uq_attempt_test_student_number'), 'test_attempts', ['test_id', 'student_id', 'number'])
    # existing tests keep today's rule: one attempt (existing attempts become number 1)
    op.add_column('tests', sa.Column('max_attempts', sa.Integer(), server_default='1', nullable=False))
    op.create_check_constraint(op.f('ck_tests_max_attempts_range'), 'tests', 'max_attempts BETWEEN 1 AND 10')


def downgrade() -> None:
    op.drop_constraint(op.f('ck_tests_max_attempts_range'), 'tests', type_='check')
    op.drop_column('tests', 'max_attempts')
    # the old schema allows one attempt per student and test: keep only the latest
    op.execute(
        "DELETE FROM test_attempts a USING test_attempts b "
        "WHERE a.test_id = b.test_id AND a.student_id = b.student_id AND a.number < b.number"
    )
    op.drop_constraint(op.f('uq_attempt_test_student_number'), 'test_attempts', type_='unique')
    op.drop_index('uq_attempt_one_in_progress', table_name='test_attempts', postgresql_where=sa.text("status = 'in_progress'"))
    op.create_unique_constraint(op.f('uq_attempt_test_student'), 'test_attempts', ['test_id', 'student_id'])
    op.drop_column('test_attempts', 'number')
    op.drop_column('test_assignments', 'extra_attempts')
