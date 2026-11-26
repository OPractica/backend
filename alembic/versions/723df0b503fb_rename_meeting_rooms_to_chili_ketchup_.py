"""rename meeting rooms to chili ketchup and boiling room

Revision ID: 723df0b503fb
Revises: a3f1c2d4e5b6
Create Date: 2026-11-26 20:14:02.270153

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "723df0b503fb"
down_revision: str | Sequence[str] | None = "a3f1c2d4e5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Data only, the schema doesn't change. The rooms live in office 1, the office
# the map and the AI assistant use. Rows that don't exist are simply not updated.
OFFICE_ID = 1
RENAMES = [("Sala 1", "Chili"), ("Sala 2", "Ketchup"), ("Sala 3", "Boiling Room")]

meeting_rooms = sa.table(
    "meeting_rooms", sa.column("office_id", sa.Integer), sa.column("alias", sa.String)
)


def rename(old: str, new: str) -> None:
    op.execute(
        meeting_rooms.update()
        .where(meeting_rooms.c.office_id == OFFICE_ID, meeting_rooms.c.alias == old)
        .values(alias=new)
    )


def upgrade() -> None:
    """Rename Sala 1, 2, 3 to Chili, Ketchup, Boiling Room."""
    for old, new in RENAMES:
        rename(old, new)


def downgrade() -> None:
    """Give the rooms back their old names."""
    for old, new in RENAMES:
        rename(new, old)
