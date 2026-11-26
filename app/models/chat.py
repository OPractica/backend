from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.database import base


class ChatSession(base):
    """Диалог пользователя с ИИ-ассистентом: вся история сообщений одной сессии."""

    __tablename__ = "ai_chat_sessions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "session_id", name="uq_ai_chat_sessions_user_session"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id", name="fk_ai_chat_sessions_user_id_users", ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Сообщения LangChain в виде JSON (messages_to_dict)
    messages: Mapped[list] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
