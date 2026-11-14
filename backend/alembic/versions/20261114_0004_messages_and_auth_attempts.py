"""messages and auth attempts

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-14 20:47:11.004849
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('auth_attempts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=300), nullable=False),
    sa.Column('attempted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_attempts'))
    )
    op.create_index('ix_auth_attempts_key_at', 'auth_attempts', ['key', 'attempted_at'], unique=False)
    op.create_table('messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('sender_user_id', sa.Integer(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('char_length(body) BETWEEN 1 AND 4000', name=op.f('ck_messages_body_length')),
    sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], name=op.f('fk_messages_sender_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['student_profiles.id'], name=op.f('fk_messages_student_id_student_profiles'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['teacher_id'], ['teacher_profiles.id'], name=op.f('fk_messages_teacher_id_teacher_profiles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_messages'))
    )
    op.create_index('ix_messages_thread_id', 'messages', ['teacher_id', 'student_id', 'id'], unique=False)
    op.create_index('ix_messages_unread', 'messages', ['teacher_id', 'student_id', 'sender_user_id'], unique=False, postgresql_where='read_at IS NULL')


def downgrade() -> None:
    op.drop_index('ix_messages_unread', table_name='messages', postgresql_where='read_at IS NULL')
    op.drop_index('ix_messages_thread_id', table_name='messages')
    op.drop_table('messages')
    op.drop_index('ix_auth_attempts_key_at', table_name='auth_attempts')
    op.drop_table('auth_attempts')
