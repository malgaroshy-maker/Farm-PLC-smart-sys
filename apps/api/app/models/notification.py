"""Notification settings and phone-push subscriptions (Milestone G3)."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class NotificationSettings(Base):
    """Single row (id='default'). The Telegram bot token stays in .env (TELEGRAM_BOT_TOKEN)."""

    __tablename__ = "notification_settings"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default="default")
    telegram_chat_id: Mapped[str | None] = mapped_column(String(40))
    # VAPID keys for web push, generated once on first use (or taken from .env)
    vapid_public_key: Mapped[str | None] = mapped_column(Text)
    vapid_private_key: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(64))
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failures: Mapped[int] = mapped_column(Integer, default=0)
