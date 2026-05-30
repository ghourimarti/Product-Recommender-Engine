"""Step 7: ORM models CRUD round-trip on aiosqlite (keyless; Postgres is the prod target)."""
from __future__ import annotations

import asyncio


def test_models_crud_roundtrip():
    async def _run():
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.db import models
        from app.db.base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            user = models.User(email="buyer@example.com")
            s.add(user)
            await s.commit()

            conv = models.Conversation(user_id=user.id, session_id="sid-1")
            s.add(conv)
            await s.commit()

            s.add_all([
                models.Message(conversation_id=conv.id, role="human", content="best earbuds?"),
                models.Message(conversation_id=conv.id, role="ai", content="The BoAt Rockerz..."),
            ])
            await s.commit()

            msgs = (await s.execute(
                select(models.Message).where(models.Message.conversation_id == conv.id)
            )).scalars().all()
            assert len(msgs) == 2
            assert {m.role for m in msgs} == {"human", "ai"}

        await engine.dispose()

    asyncio.run(_run())
