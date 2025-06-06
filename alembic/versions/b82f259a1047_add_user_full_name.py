"""add user full name

Revision ID: b82f259a1047
Revises: 96daa7d0cd30
Create Date: 2025-06-04 05:49:30.552175

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b82f259a1047'
down_revision: Union[str, None] = '96daa7d0cd30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('full_name', sa.String(), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'full_name')
    # ### end Alembic commands ###
