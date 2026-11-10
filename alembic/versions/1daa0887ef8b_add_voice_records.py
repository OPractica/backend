"""Add voice records.

Revision ID: 1daa0887ef8b
Revises: 58dec2002bab
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "1daa0887ef8b"
down_revision: str | Sequence[str] | None = "58dec2002bab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voice_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("audio_path", sa.String(length=500), nullable=False),
        sa.Column("transcription", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_voice_records_expires_at",
        "voice_records",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_voice_records_expires_at",
        table_name="voice_records",
    )

    op.drop_table("voice_records")
