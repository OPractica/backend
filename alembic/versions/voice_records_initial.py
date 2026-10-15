
"""Create voice_records table.

Revision ID: voice_records_001
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "voice_records_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "voice_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("audio_path", sa.String(500), nullable=False),
        sa.Column("transcription", sa.Text(), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
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
    )


def downgrade():
    op.drop_index(
        "ix_voice_records_expires_at",
        table_name="voice_records",
    )
    op.drop_table("voice_records")
