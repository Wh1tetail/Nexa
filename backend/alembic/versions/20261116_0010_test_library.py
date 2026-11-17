"""test library

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-16 23:40:04.405549
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('test_sections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('position', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['parent_id'], ['test_sections.id'], name=op.f('fk_test_sections_parent_id_test_sections'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_test_sections'))
    )
    op.create_index(op.f('ix_test_sections_parent_id'), 'test_sections', ['parent_id'], unique=False)
    op.create_table('test_tags',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_test_tags')),
    sa.UniqueConstraint('name', name=op.f('uq_test_tags_name'))
    )
    op.create_table('test_section_links',
    sa.Column('test_id', sa.Integer(), nullable=False),
    sa.Column('section_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['section_id'], ['test_sections.id'], name=op.f('fk_test_section_links_section_id_test_sections'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['test_id'], ['tests.id'], name=op.f('fk_test_section_links_test_id_tests'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('test_id', 'section_id', name=op.f('pk_test_section_links'))
    )
    op.create_index(op.f('ix_test_section_links_section_id'), 'test_section_links', ['section_id'], unique=False)
    op.create_table('test_tag_links',
    sa.Column('test_id', sa.Integer(), nullable=False),
    sa.Column('tag_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['tag_id'], ['test_tags.id'], name=op.f('fk_test_tag_links_tag_id_test_tags'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['test_id'], ['tests.id'], name=op.f('fk_test_tag_links_test_id_tests'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('test_id', 'tag_id', name=op.f('pk_test_tag_links'))
    )
    op.create_index(op.f('ix_test_tag_links_tag_id'), 'test_tag_links', ['tag_id'], unique=False)
    op.add_column('tests', sa.Column('is_library', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('tests', sa.Column('published', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('tests', sa.Column('author_id', sa.Integer(), nullable=True))
    op.add_column('tests', sa.Column('level', sa.Enum('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='english_level', native_enum=False, create_constraint=True, length=32), nullable=True))
    op.add_column('tests', sa.Column('source_test_id', sa.Integer(), nullable=True))
    op.add_column('tests', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    op.alter_column('tests', 'teacher_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.create_index(op.f('ix_tests_author_id'), 'tests', ['author_id'], unique=False)
    op.create_index(op.f('ix_tests_is_library'), 'tests', ['is_library'], unique=False)
    op.create_foreign_key(op.f('fk_tests_source_test_id_tests'), 'tests', 'tests', ['source_test_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_tests_author_id_users'), 'tests', 'users', ['author_id'], ['id'], ondelete='SET NULL')
    op.create_check_constraint(
        op.f('ck_tests_owner_kind'), 'tests',
        '(is_library AND teacher_id IS NULL) OR (NOT is_library AND teacher_id IS NOT NULL)',
    )
    op.drop_constraint(op.f('ck_users_user_role'), 'users', type_='check')
    op.create_check_constraint(op.f('ck_users_user_role'), 'users', "role IN ('student', 'teacher', 'admin', 'methodist')")

    # starting structure of the library (methodists can rename, add and delete)
    sections = sa.table('test_sections', sa.column('id', sa.Integer), sa.column('parent_id', sa.Integer),
                        sa.column('name', sa.String), sa.column('position', sa.Integer))
    conn = op.get_bind()
    for pos, (name, children) in enumerate({'Grammar': ['Present Simple', 'Present Continuous', 'Past Simple', 'Future Forms', 'Modal Verbs', 'Conditionals'], 'Vocabulary': ['Food', 'Travel', 'Work', 'Education', 'Technology'], 'Reading': ['Short Texts', 'Long Texts', 'Articles'], 'Listening': ['Daily Conversations', 'Interviews', 'Dialogues'], 'Writing': [], 'Speaking': [], 'Mixed Tests': []}.items()):
        parent = conn.execute(
            sa.insert(sections).values(name=name, position=pos, parent_id=None).returning(sections.c.id)
        ).scalar_one()
        for cpos, child in enumerate(children):
            conn.execute(sa.insert(sections).values(name=child, position=cpos, parent_id=parent))


def downgrade() -> None:
    # the old schema has no library tests and no methodists (their data goes)
    op.execute('DELETE FROM tests WHERE is_library')
    op.execute("DELETE FROM users WHERE role = 'methodist'")
    op.drop_constraint(op.f('ck_users_user_role'), 'users', type_='check')
    op.create_check_constraint(op.f('ck_users_user_role'), 'users', "role IN ('student', 'teacher', 'admin')")
    op.drop_constraint(op.f('ck_tests_owner_kind'), 'tests', type_='check')
    op.drop_constraint(op.f('fk_tests_author_id_users'), 'tests', type_='foreignkey')
    op.drop_constraint(op.f('fk_tests_source_test_id_tests'), 'tests', type_='foreignkey')
    op.drop_index(op.f('ix_tests_is_library'), table_name='tests')
    op.drop_index(op.f('ix_tests_author_id'), table_name='tests')
    op.alter_column('tests', 'teacher_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.drop_column('tests', 'updated_at')
    op.drop_column('tests', 'source_test_id')
    op.drop_column('tests', 'level')
    op.drop_column('tests', 'author_id')
    op.drop_column('tests', 'published')
    op.drop_column('tests', 'is_library')
    op.drop_index(op.f('ix_test_tag_links_tag_id'), table_name='test_tag_links')
    op.drop_table('test_tag_links')
    op.drop_index(op.f('ix_test_section_links_section_id'), table_name='test_section_links')
    op.drop_table('test_section_links')
    op.drop_table('test_tags')
    op.drop_index(op.f('ix_test_sections_parent_id'), table_name='test_sections')
    op.drop_table('test_sections')
