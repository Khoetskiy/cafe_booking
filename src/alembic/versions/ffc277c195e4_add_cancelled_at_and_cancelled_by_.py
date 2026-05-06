"""add cancelled_at and cancelled_by fields in booking model

Revision ID: ffc277c195e4
Revises: 98b2bfe0b806
Create Date: 2026-05-06 17:47:05.017045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ffc277c195e4'
down_revision: Union[str, Sequence[str], None] = '98b2bfe0b806'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
