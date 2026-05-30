"""Aggregate API router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import admin, chat, health, metrics

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(metrics.router)
api_router.include_router(chat.router)
api_router.include_router(admin.router)
