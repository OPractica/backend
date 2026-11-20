"""prevent double booking in db

Revision ID: 4e6f5b93ce00
Revises: 1daa0887ef8b
Create Date: 2026-11-11 15:30:43.005557

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4e6f5b93ce00"
down_revision: str | Sequence[str] | None = "1daa0887ef8b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_check_constraint(
        "ck_bookings_ends_after_starts",
        "bookings",
        "ends_at > starts_at",
    )
    op.create_exclude_constraint(
        "excl_bookings_no_overlap",
        "bookings",
        (sa.column("seat_id"), "="),
        (
            sa.func.tstzrange(sa.column("starts_at"), sa.column("ends_at"), "[)"),
            "&&",
        ),
        using="gist",
        where=sa.text("status = 'confirmed'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("excl_bookings_no_overlap", "bookings")
    op.drop_constraint("ck_bookings_ends_after_starts", "bookings", type_="check")
