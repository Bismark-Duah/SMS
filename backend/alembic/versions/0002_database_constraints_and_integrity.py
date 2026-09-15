"""Database constraints and integrity

Revision ID: 0002_constraints
Revises: 0001_baseline
Create Date: 2026-09-15 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from backend.app.database import Base

# revision identifiers, used by Alembic.
revision: str = '0002_constraints'
down_revision: Union[str, None] = '0001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure all tables and constraints are synchronized
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    pass
