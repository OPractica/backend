"""Add user ownership to voice records.

Revision ID: b8c0a5d4e712
Revises: 4e6f5b93ce00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8c0a5d4e712"
down_revision: str | Sequence[str] | None = "4e6f5b93ce00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "voice_records",
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_voice_records_user_id_users",
        "voice_records",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_voice_records_user_id",
        "voice_records",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_voice_records_user_id",
        table_name="voice_records",
    )

    op.drop_constraint(
        "fk_voice_records_user_id_users",
        "voice_records",
        type_="foreignkey",
    )

    op.drop_column(
        "voice_records",
        "user_id",
    )
