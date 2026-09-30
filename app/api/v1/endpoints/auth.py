import uuid
import logging
from datetime import datetime, timezone
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel, EmailStr, Field

from utils.jwt import generate_access_token
from core.database import get_database
from core.settings import settings
from utils.cookie import set_access_token_cookie

logger = logging.getLogger(__name__)

auth_routes = APIRouter(prefix="/auth", tags=["Auth Routes"])

oauth = OAuth()
if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    # Use explicit redirect URI to avoid proxy issues
    redirect_uri = getattr(settings, "GOOGLE_CALLBACK_URL", "http://localhost:8000/api/v1/auth/google/callback")
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
        redirect_uri=redirect_uri,
    )


class EmailSignupRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=60)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str


# ------------------ EMAIL / PASSWORD SIGNUP & LOGIN ------------------

@auth_routes.post("/signup")
async def signup_with_email(payload: EmailSignupRequest, response: Response, db=Depends(get_database)):
    """Registers a new restaurant owner or user with email and hashed password."""
    email_clean = payload.email.strip().lower()
    users = db["users"]

    existing = await users.find_one({"email": email_clean})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    # Hash password using bcrypt
    hashed_password = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user_id = f"usr_{str(uuid.uuid4())[:8]}"

    new_user = {
        "user_id": user_id,
        "full_name": payload.full_name.strip(),
        "email": email_clean,
        "password": hashed_password,
        "role": "OWNER",
        "is_onboarded": False,
        "active_tenant_id": None,
        "tenants": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    await users.insert_one(new_user)

    access_token = generate_access_token(user_id)
    set_access_token_cookie(response=response, token=access_token)

    return {
        "status": "success",
        "message": "Account created successfully.",
        "user": {
            "user_id": user_id,
            "full_name": new_user["full_name"],
            "email": email_clean,
            "role": new_user["role"],
            "is_onboarded": False,
        },
        "token": access_token
    }


@auth_routes.post("/login")
async def login_with_email(payload: EmailLoginRequest, response: Response, db=Depends(get_database)):
    """Logs in an existing user with email and password."""
    email_clean = payload.email.strip().lower()
    users = db["users"]

    user = await users.find_one({"email": email_clean})
    if not user or "password" not in user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # Verify bcrypt password
    is_valid = bcrypt.checkpw(payload.password.encode("utf-8"), user["password"].encode("utf-8"))
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    user_id = user["user_id"]
    await users.update_one(
        {"user_id": user_id},
        {"$set": {"last_login": datetime.now(timezone.utc)}}
    )

    access_token = generate_access_token(user_id)
    set_access_token_cookie(response=response, token=access_token)

    return {
        "status": "success",
        "message": "Logged in successfully.",
        "user": {
            "user_id": user_id,
            "full_name": user.get("full_name", ""),
            "email": email_clean,
            "role": user.get("role", "OWNER"),
            "is_onboarded": user.get("is_onboarded", False),
            "active_tenant_id": user.get("active_tenant_id"),
        },
        "token": access_token
    }


@auth_routes.post("/logout")
async def logout(response: Response):
    """Logs out user by clearing the access token cookie."""
    from utils.cookie import clear_access_token_cookie
    clear_access_token_cookie(response)
    return {"status": "success", "message": "Logged out successfully."}


@auth_routes.get("/me")
async def get_current_user(request: Request, database=Depends(get_database)):
    """Get current authenticated user from cookie token."""
    from middlewares.auth_middleware import get_current_user
    user = await get_current_user(request, database)
    user.pop("password", None)
    user.pop("google_id", None)
    return user


@auth_routes.post("/switch-tenant")
async def switch_tenant(payload: dict, database=Depends(get_database), current_user: dict = Depends(get_current_user)):
    """Switch active tenant for the user."""
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id required")
    
    # Verify user has access to this tenant
    if tenant_id not in current_user.get("tenants", []):
        raise HTTPException(status_code=403, detail="No access to this tenant")
    
    await database["users"].update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {"active_tenant_id": tenant_id, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"status": "success", "active_tenant_id": tenant_id}


@auth_routes.post("/complete-onboarding")
async def complete_onboarding(payload: dict, database=Depends(get_database), current_user: dict = Depends(get_current_user)):
    """Mark user as onboarded after completing restaurant setup."""
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id required")
    
    # Verify user has access to this tenant
    if tenant_id not in current_user.get("tenants", []):
        raise HTTPException(status_code=403, detail="No access to this tenant")
    
    await database["users"].update_one(
        {"user_id": current_user["user_id"]},
        {"$set": {
            "is_onboarded": True,
            "active_tenant_id": tenant_id,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    return {"status": "success", "message": "Onboarding completed"}


# ------------------ GOOGLE OAUTH FLOW ------------------

@auth_routes.get("/google")
async def login_with_google(request: Request):
    """Initiates Google OAuth authentication redirect."""
    # Use explicit redirect_uri registered in Google Cloud Console
    redirect_uri = getattr(settings, "GOOGLE_CALLBACK_URL", "http://localhost:8000/api/v1/auth/google/callback")
    logger.info(f"[google] Initiating OAuth with redirect_uri: {redirect_uri}")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@auth_routes.get("/google/callback", name="google_callback_handler")
async def google_callback_handler(request: Request, database=Depends(get_database)):
    """Handles callback from Google OAuth."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"OAuth verification error: {str(e)}"
        )

    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(
            status_code=400, detail="Could not retrieve profile from Google."
        )

    google_id = user_info["sub"]
    email = user_info["email"].lower()
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")

    users = database["users"]
    user = await users.find_one({"google_id": google_id})

    if not user:
        user_id = f"usr_{str(uuid.uuid4())[:8]}"
        new_user = {
            "user_id": user_id,
            "full_name": name,
            "email": email,
            "google_id": google_id,
            "profile_picture": picture,
            "role": "OWNER",
            "is_onboarded": False,
            "active_tenant_id": None,
            "tenants": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        await users.insert_one(new_user)
    else:
        user_id = user["user_id"]
        await users.update_one(
            {"user_id": user_id},
            {"$set": {"last_login": datetime.now(timezone.utc)}}
        )

    access_token = generate_access_token(user_id)
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    redirect_target = f"{frontend_url}/dashboard"

    response = RedirectResponse(url=redirect_target)
    set_access_token_cookie(response=response, token=access_token)
    return response