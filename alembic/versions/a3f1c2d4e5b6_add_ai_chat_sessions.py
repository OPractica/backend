"""Add AI chat sessions.

Revision ID: a3f1c2d4e5b6
Revises: e369c7a10cf4
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3f1c2d4e5b6"
down_revision: str | Sequence[str] | None = "e369c7a10cf4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_chat_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_ai_chat_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id", "session_id", name="uq_ai_chat_sessions_user_session"
        ),
    )
    op.create_index("ix_ai_chat_sessions_user_id", "ai_chat_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_chat_sessions_user_id", "ai_chat_sessions")
    op.drop_table("ai_chat_sessions")
