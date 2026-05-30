
# <---------------------------------------------->
#                  Import Modules
# <---------------------------------------------->

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()
http_bearer = HTTPBearer()


# <---------------------------------------------->
#            Import _hash(password: str)
# <---------------------------------------------->

def _hash(password: str) -> str:
    print(f"password = {password}")
    print(f"password.encode() = {password.encode()}")
    print(f"password.encode() = {password.encode().decode()}")
    print(f"bcrypt.gensalt() = {bcrypt.gensalt()}")
    print(f"bcrypt.gensalt().decode() = {bcrypt.gensalt().decode()}")
    print(f"bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode() = {bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()}\n\n")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# Demo user store — in production replace with database + proper user service
USERS_DB: dict[str, dict] = {
    "admin": {
        "username": "admin",
        "hashed_password": _hash("admin123"),
        "role": "admin",
    },
    "user": {
        "username": "user",
        "hashed_password": _hash("user123"),
        "role": "user",
    },
}

# <---------------------------------------------->
#     verify_password(plain: str, hashed: str)
# <---------------------------------------------->

def verify_password(plain: str, hashed: str) -> bool:
    print(f"plain = {plain}")
    print(f"hashed = {hashed}")
    print(f"plain.encode() = {plain.encode()}")
    print(f"hashed.encode() = {hashed.encode()}")
    print(f"bcrypt.checkpw(plain.encode(), hashed.encode()")
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# <---------------------------------------------->
#  authenticate_user()
# <---------------------------------------------->

def authenticate_user(username: str, password: str) -> Opti*/onal[dict]:
    user = USERS_DB.get(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user

# <---------------------------------------------->
#                create_access_token()
# <---------------------------------------------->

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# <---------------------------------------------->
# Import Modules
# <---------------------------------------------->

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(http_bearer),
) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        username: str = payload.get("sub", "")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        user = USERS_DB.get(username)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
