"""add completed_at and completed_by fields in booking model

Revision ID: 13960fcd11f2
Revises: a642189c888f
Create Date: 2026-05-06 18:07:09.210670

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13960fcd11f2'
down_revision: Union[str, Sequence[str], None] = 'a642189c888f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def upgrade():
    op.add_column(
        'booking',
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'booking',
        sa.Column('completed_by', sa.Integer(), nullable=True),
    )

def downgrade() -> None:
    """Downgrade schema."""
    pass
