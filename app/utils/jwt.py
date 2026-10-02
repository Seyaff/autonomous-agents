from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, status
from core.settings import settings


def generate_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=60),
        "iss": "Siyaf",
        "type": "access",
    }

    token = jwt.encode(
        payload,
        key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    return token




def verify_jwt_token(token:str):
    payload = jwt.decode(
        token,
        key=settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
        
        
    return user_id