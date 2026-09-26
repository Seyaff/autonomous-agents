import jwt
from fastapi import Request, Depends, HTTPException, status
from core.database import get_database
from api.v1.auth.jwt import verify_jwt_token

async def get_current_user(request: Request, database=Depends(get_database)):
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (missing cookie)",
        )

    try:
        user_id = verify_jwt_token(token)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    user = await database["users"].find_one({"user_id": user_id})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if "_id" in user:
        user["_id"] = str(user["_id"])

    return user

