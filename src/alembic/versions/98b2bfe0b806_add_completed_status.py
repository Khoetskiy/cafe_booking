"""add completed status

Revision ID: 98b2bfe0b806
Revises: c62f6a4d21c4
Create Date: 2026-05-03 19:58:32.812687

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98b2bfe0b806'
down_revision: Union[str, Sequence[str], None] = 'c62f6a4d21c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE booking_status_enum ADD VALUE 'COMPLETED'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
