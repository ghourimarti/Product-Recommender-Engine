from datetime import timedelta

from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.core.security import authenticate_user, create_access_token
from app.schemas.request import AuthRequest
from app.schemas.response import TokenResponse

router = APIRouter(tags=["auth"])
settings = get_settings()


@router.post("/auth/token", response_model=TokenResponse, summary="Obtain JWT access token")
async def login(form: AuthRequest) -> TokenResponse:
    user = authenticate_user(form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
