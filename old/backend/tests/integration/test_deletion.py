"""Phase 5: GDPR right-to-be-forgotten deletes all of a user's data."""
from __future__ import annotations

import asyncio


def test_delete_user_data_cascades():
    async def _run():
        from sqlalchemy import func, select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.db import models
        from app.db.base import Base
        from app.db.deletion import delete_user_data

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sm = async_sessionmaker(engine, expire_on_commit=False)

        async with sm() as s:
            user = models.User(email="forgetme@example.com")
            other = models.User(email="keep@example.com")
            s.add_all([user, other])
            await s.commit()

            conv = models.Conversation(user_id=user.id, session_id="s1")
            keep_conv = models.Conversation(user_id=other.id, session_id="s2")
            s.add_all([conv, keep_conv])
            await s.commit()

            msg = models.Message(conversation_id=conv.id, role="human", content="hi")
            s.add(msg)
            await s.commit()
            s.add(models.Feedback(message_id=msg.id, rating=1))
            await s.commit()

            result = await delete_user_data(s, user.id, user_sub="cognito-sub-1")
            assert result == {"conversations": 1, "messages": 1}

            # target user's data gone
            assert (await s.execute(select(func.count()).select_from(models.Message))).scalar() == 0
            assert (await s.execute(select(func.count()).select_from(models.Feedback))).scalar() == 0
            # other user's conversation preserved
            users = (await s.execute(select(models.User))).scalars().all()
            assert [u.email for u in users] == ["keep@example.com"]
            convs = (await s.execute(select(models.Conversation))).scalars().all()
            assert len(convs) == 1 and convs[0].user_id == other.id

        await engine.dispose()

    asyncio.run(_run())
