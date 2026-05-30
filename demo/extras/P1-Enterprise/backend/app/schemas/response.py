from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float


class UsageResponse(BaseModel):
    total_requests: int
    total_cost_usd: float
    avg_cost_per_request_usd: float


class CostResponse(BaseModel):
    total_cost_usd: float
    avg_cost_per_request_usd: float
    estimated_monthly_cost_usd: float
