"""merge meeting rooms and voice records heads

Revision ID: e369c7a10cf4
Revises: 7c3a1e5b9d20, b8c0a5d4e712
Create Date: 2026-11-20 16:24:29.508017

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "e369c7a10cf4"
down_revision: str | Sequence[str] | None = ("7c3a1e5b9d20", "b8c0a5d4e712")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the two branches; no schema changes."""


def downgrade() -> None:
    """Split the two branches again; no schema changes."""
