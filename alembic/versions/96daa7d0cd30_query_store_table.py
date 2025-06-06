"""query store table

Revision ID: 96daa7d0cd30
Revises: 5cb720b98f21
Create Date: 2025-06-01 18:52:05.182696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96daa7d0cd30'
down_revision: Union[str, None] = '5cb720b98f21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('query_store',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('question', sa.String(), nullable=True),
    sa.Column('generated_sql', sa.String(), nullable=True),
    sa.Column('response_type', sa.String(), nullable=True),
    sa.Column('answer_template', sa.String(), nullable=True),
    sa.Column('display_type', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_query_store_id'), 'query_store', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_query_store_id'), table_name='query_store')
    op.drop_table('query_store')
    # ### end Alembic commands ###
