"""Admin routes (RBAC-protected). Includes the GDPR data-deletion endpoint."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_role
from app.db.deletion import delete_user_data
from app.db.session import get_db

router = APIRouter(tags=["admin"], prefix="/admin")


@router.delete("/users/{user_id}", dependencies=[Depends(require_role("admin"))])
async def delete_user(user_id: uuid.UUID, sub: str | None = None, db: AsyncSession = Depends(get_db)) -> dict:
    """Right-to-be-forgotten: erase a user's personal data (admin only)."""
    result = await delete_user_data(db, user_id, user_sub=sub)
    return {"deleted": True, **result}
