from fastapi import APIRouter, Response , HTTPException , status, Depends, Request
from core.database import get_database
from utils.jwt import verify_jwt_token
import jwt
from middlewares.auth_middleware import get_current_user




user_routes = APIRouter(prefix="/user" , tags=["User Routes"])



@user_routes.get("/me")
async def get_me(request: Request, database=Depends(get_database) , user = Depends(get_current_user)):
    
    return user