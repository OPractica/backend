"""add meeting rooms

Revision ID: 7c3a1e5b9d20
Revises: 4e6f5b93ce00
Create Date: 2026-11-18 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c3a1e5b9d20"
down_revision: str | Sequence[str] | None = "4e6f5b93ce00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "meeting_rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("office_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("alias", sa.String(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("equipments", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_index("ix_meeting_rooms_id", "meeting_rooms", ["id"])
    op.create_index("ix_meeting_rooms_office_id", "meeting_rooms", ["office_id"])

    op.create_table(
        "meeting_room_bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "room_id",
            sa.Integer(),
            sa.ForeignKey("meeting_rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.CheckConstraint(
            "ends_at > starts_at",
            name="ck_meeting_room_bookings_ends_after_starts",
        ),
    )
    op.create_index("ix_meeting_room_bookings_id", "meeting_room_bookings", ["id"])
    # btree_gist is created by 4e6f5b93ce00
    op.create_exclude_constraint(
        "excl_meeting_room_bookings_no_overlap",
        "meeting_room_bookings",
        (sa.column("room_id"), "="),
        (
            sa.func.tstzrange(sa.column("starts_at"), sa.column("ends_at"), "[)"),
            "&&",
        ),
        using="gist",
        where=sa.text("status = 'confirmed'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("meeting_room_bookings")
    op.drop_index("ix_meeting_rooms_office_id", "meeting_rooms")
    op.drop_index("ix_meeting_rooms_id", "meeting_rooms")
    op.drop_table("meeting_rooms")
