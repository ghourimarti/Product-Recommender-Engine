from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.observability.cost_tracker import cost_tracker
from app.schemas.response import CostResponse, UsageResponse

router = APIRouter(tags=["admin"])


def _require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


@router.get("/admin/usage", response_model=UsageResponse, summary="Total usage stats (admin only)")
async def get_usage(_: dict = Depends(_require_admin)) -> UsageResponse:
    summary = cost_tracker.get_summary()
    return UsageResponse(**{k: summary[k] for k in UsageResponse.model_fields})


@router.get("/admin/cost", response_model=CostResponse, summary="Cost breakdown (admin only)")
async def get_cost(_: dict = Depends(_require_admin)) -> CostResponse:
    summary = cost_tracker.get_summary()
    return CostResponse(
        total_cost_usd=summary["total_cost_usd"],
        avg_cost_per_request_usd=summary["avg_cost_per_request_usd"],
        estimated_monthly_cost_usd=round(
            summary["avg_cost_per_request_usd"] * max(summary["total_requests"], 1) * 30, 4
        ),
    )
