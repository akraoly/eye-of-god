from datetime import datetime, timedelta, timezone
import jwt
from app.config import settings


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        settings.JWT_SECRET,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> int:
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    return int(payload["sub"])
