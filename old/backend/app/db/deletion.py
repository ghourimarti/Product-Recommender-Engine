"""Right-to-be-forgotten / GDPR data deletion (Phase 5 hardening).

Deletes all of a user's personal data in dependency order within one transaction:
feedback -> messages -> conversations -> user, plus a best-effort purge of the LangChain
chat-history rows for that user's namespaced sessions.
"""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.observability.logger import get_logger

logger = get_logger(__name__)


async def delete_user_data(session: AsyncSession, user_id: uuid.UUID, user_sub: str | None = None) -> dict:
    conv_ids = (
        await session.execute(select(models.Conversation.id).where(models.Conversation.user_id == user_id))
    ).scalars().all()

    msg_ids: list = []
    if conv_ids:
        msg_ids = (
            await session.execute(select(models.Message.id).where(models.Message.conversation_id.in_(conv_ids)))
        ).scalars().all()
        if msg_ids:
            await session.execute(delete(models.Feedback).where(models.Feedback.message_id.in_(msg_ids)))
            await session.execute(delete(models.Message).where(models.Message.id.in_(msg_ids)))
        await session.execute(delete(models.Conversation).where(models.Conversation.id.in_(conv_ids)))

    await session.execute(delete(models.User).where(models.User.id == user_id))

    # Best-effort: purge LangChain history rows for this user's namespaced sessions.
    if user_sub:
        try:
            await session.execute(
                text("DELETE FROM message_store WHERE session_id LIKE :p"), {"p": f"{user_sub}:%"}
            )
        except Exception:  # noqa: BLE001 - table may not exist in some envs
            logger.warning("message_store_purge_skipped")

    await session.commit()
    logger.info("user_data_deleted", extra={"conversations": len(conv_ids), "messages": len(msg_ids)})
    return {"conversations": len(conv_ids), "messages": len(msg_ids)}
