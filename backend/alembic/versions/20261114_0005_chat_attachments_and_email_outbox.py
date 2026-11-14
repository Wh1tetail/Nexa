"""chat attachments and email outbox

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-14 21:12:09.602857
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('attachments', sa.Column('message_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_attachments_message_id'), 'attachments', ['message_id'], unique=False)
    op.create_foreign_key(op.f('fk_attachments_message_id_messages'), 'attachments', 'messages', ['message_id'], ['id'], ondelete='CASCADE')
    op.add_column('messages', sa.Column('email_processed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_messages_email_pending', 'messages', ['id'], unique=False, postgresql_where='email_processed_at IS NULL')
    op.add_column('notifications', sa.Column('email_processed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_notifications_email_pending', 'notifications', ['id'], unique=False, postgresql_where='email_processed_at IS NULL')
    op.add_column('users', sa.Column('email_prefs', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))

    # a chat message may now be files only (empty text)
    op.drop_constraint(op.f('ck_messages_body_length'), 'messages', type_='check')
    op.create_check_constraint(op.f('ck_messages_body_length'), 'messages', 'char_length(body) <= 4000')
    # attachments get a third possible owner
    op.drop_constraint(op.f('ck_attachments_single_owner'), 'attachments', type_='check')
    op.create_check_constraint(
        op.f('ck_attachments_single_owner'), 'attachments',
        '(homework_id IS NOT NULL)::int + (submission_id IS NOT NULL)::int + (message_id IS NOT NULL)::int = 1',
    )
    # everything that existed before the outbox counts as handled: no e-mail burst on deploy
    op.execute('UPDATE notifications SET email_processed_at = now()')
    op.execute('UPDATE messages SET email_processed_at = now()')


def downgrade() -> None:
    # chat files and file-only messages cannot exist under the old constraints
    # (their stored objects stay in storage; this is a schema rollback only)
    op.execute('DELETE FROM attachments WHERE message_id IS NOT NULL')
    op.execute("DELETE FROM messages WHERE body = ''")
    op.drop_constraint(op.f('ck_attachments_single_owner'), 'attachments', type_='check')
    op.create_check_constraint(
        op.f('ck_attachments_single_owner'), 'attachments',
        '(homework_id IS NOT NULL)::int + (submission_id IS NOT NULL)::int = 1',
    )
    op.drop_constraint(op.f('ck_messages_body_length'), 'messages', type_='check')
    op.create_check_constraint(op.f('ck_messages_body_length'), 'messages', 'char_length(body) BETWEEN 1 AND 4000')
    op.drop_column('users', 'email_prefs')
    op.drop_index('ix_notifications_email_pending', table_name='notifications', postgresql_where='email_processed_at IS NULL')
    op.drop_column('notifications', 'email_processed_at')
    op.drop_index('ix_messages_email_pending', table_name='messages', postgresql_where='email_processed_at IS NULL')
    op.drop_column('messages', 'email_processed_at')
    op.drop_constraint(op.f('fk_attachments_message_id_messages'), 'attachments', type_='foreignkey')
    op.drop_index(op.f('ix_attachments_message_id'), table_name='attachments')
    op.drop_column('attachments', 'message_id')
