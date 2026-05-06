"""add cancelled_at and cancelled_by fields in booking model

Revision ID: a642189c888f
Revises: ffc277c195e4
Create Date: 2026-05-06 17:51:55.211080

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a642189c888f'
down_revision: Union[str, Sequence[str], None] = 'ffc277c195e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        'booking',
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'booking',
        sa.Column('cancelled_by', sa.Integer(), nullable=True),
    )

def downgrade() -> None:
    """Downgrade schema."""
    pass
