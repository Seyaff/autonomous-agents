import uuid
import logging
from datetime import datetime, timezone
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel, EmailStr, Field

from utils.jwt import generate_access_token
from middlewares.auth_middleware import get_current_user as require_signed_in
from services.sessions import create_session, revoke_all, revoke_session, rotate, hash_token, SESSIONS
from services import email as mail
from utils.jwt import verify_access_claims
from typing import Optional
from core.database import get_database
from core.settings import settings
from utils.cookie import (
    REFRESH_COOKIE,
    clear_access_token_cookie,
    clear_refresh_token_cookie,
    set_access_token_cookie,
    set_refresh_token_cookie,
)

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


class FounderBootstrapRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=60)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    secret: str = Field(..., description="Must match the FOUNDER_BOOTSTRAP_SECRET env var")


# ------------------ EMAIL / PASSWORD SIGNUP & LOGIN ------------------

async def _start_session(response: Response, request: Request, db, user_id: str) -> str:
    """Starts a session for a sign-in, sets the access and refresh cookies, and returns the access token.
    A sign-in from a device this account hasn't used before is reported by email."""
    device = request.headers.get("user-agent", "")
    seen_before = await db[SESSIONS].find_one({"user_id": user_id}, {"_id": 1})
    same_device = await db[SESSIONS].find_one({"user_id": user_id, "user_agent": device[:300]}, {"_id": 1})
    session, refresh = await create_session(db, user_id, device)
    if seen_before and not same_device:
        user = await db["users"].find_one({"user_id": user_id}, {"email": 1})
        if user and user.get("email"):
            mail.new_sign_in(user["email"], user_id, datetime.now(timezone.utc), device[:120])
    access_token = generate_access_token(user_id, session["session_id"])
    set_access_token_cookie(response=response, token=access_token)
    set_refresh_token_cookie(response=response, token=refresh)
    return access_token


@auth_routes.post("/signup")
async def signup_with_email(payload: EmailSignupRequest, request: Request, response: Response, db=Depends(get_database)):
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
    mail.welcome(new_user["email"], new_user["full_name"], user_id)

    access_token = await _start_session(response, request, db, user_id)

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
async def login_with_email(payload: EmailLoginRequest, request: Request, response: Response, db=Depends(get_database)):
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

    access_token = await _start_session(response, request, db, user_id)

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


@auth_routes.post("/bootstrap-founder")
async def bootstrap_founder(
    payload: FounderBootstrapRequest, request: Request, response: Response, db=Depends(get_database)
):
    """
    One-time setup route that creates the single FOUNDER account. There is
    no public founder signup — this is it, and it permanently disables
    itself the moment a FOUNDER account exists.
    """
    if not settings.FOUNDER_BOOTSTRAP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Founder bootstrap is disabled.",
        )
    if payload.secret != settings.FOUNDER_BOOTSTRAP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid bootstrap secret.",
        )

    users = db["users"]

    if await users.find_one({"role": "FOUNDER"}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A founder account already exists.",
        )

    email_clean = payload.email.strip().lower()
    if await users.find_one({"email": email_clean}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    hashed_password = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user_id = f"usr_{str(uuid.uuid4())[:8]}"

    new_user = {
        "user_id": user_id,
        "full_name": payload.full_name.strip(),
        "email": email_clean,
        "password": hashed_password,
        "role": "FOUNDER",
        "is_onboarded": True,
        "active_tenant_id": None,
        "tenants": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await users.insert_one(new_user)

    access_token = await _start_session(response, request, db, user_id)

    return {
        "status": "success",
        "message": "Founder account created.",
        "user": {
            "user_id": user_id,
            "full_name": new_user["full_name"],
            "email": email_clean,
            "role": "FOUNDER",
        },
        "token": access_token,
    }


@auth_routes.post("/refresh")
async def refresh_session(request: Request, response: Response, db=Depends(get_database)):
    """Trades the refresh cookie for a new access token and a new refresh token.
    The browser calls this when its access token has run out. Nothing else is needed."""
    refresh = request.cookies.get(REFRESH_COOKIE)
    if not refresh:
        clear_access_token_cookie(response)
        raise HTTPException(status_code=401, detail="Not signed in.")

    session, new_refresh, problem = await rotate(db, refresh)
    if problem:
        clear_access_token_cookie(response)
        clear_refresh_token_cookie(response)
        detail = "Your session was signed out on another device. Please sign in again." if problem == "reused" else "Your session has ended. Please sign in again."
        raise HTTPException(status_code=401, detail=detail)

    set_access_token_cookie(response=response, token=generate_access_token(session["user_id"], session["session_id"]))
    set_refresh_token_cookie(response=response, token=new_refresh)
    return {"status": "success"}


@auth_routes.post("/logout")
async def logout(request: Request, response: Response, db=Depends(get_database)):
    """Signs out this device only. The session stops working at once."""
    refresh = request.cookies.get(REFRESH_COOKIE)
    if refresh:
        session = await db[SESSIONS].find_one({"refresh_hash": hash_token(refresh)}, {"session_id": 1})
        if session:
            await revoke_session(db, session["session_id"], reason="signed_out")
    clear_access_token_cookie(response)
    clear_refresh_token_cookie(response)
    return {"status": "success", "message": "Logged out successfully."}


@auth_routes.post("/logout-all")
async def logout_everywhere(
    response: Response,
    current_user: dict = Depends(require_signed_in),
    db=Depends(get_database),
):
    """Signs out every device, including this one."""
    await revoke_all(db, current_user["user_id"], reason="signed_out_everywhere")
    clear_access_token_cookie(response)
    clear_refresh_token_cookie(response)
    return {"status": "success", "message": "Signed out everywhere."}


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


# ------------------ GOOGLE OAUTH FLOW ------------------

@auth_routes.get("/google")
async def login_with_google(request: Request):
    """Initiates Google OAuth authentication redirect."""
    # Use explicit redirect_uri registered in Google Cloud Console
    redirect_uri = getattr(settings, "GOOGLE_CALLBACK_URL", "http://localhost:8000/api/v1/auth/google/callback")
    
    # Get next parameter from query string
    next_param = request.query_params.get("next", "/setup")
    logger.info(f"[google] Initiating OAuth with redirect_uri: {redirect_uri}, next: {next_param}")
    
    # Pass next parameter via state to preserve it through OAuth flow
    return await oauth.google.authorize_redirect(request, redirect_uri, state=next_param)


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
        mail.welcome(email, name or email, user_id)
        user = new_user
    else:
        user_id = user["user_id"]
        await users.update_one(
            {"user_id": user_id},
            {"$set": {"last_login": datetime.now(timezone.utc)}}
        )

    # Check if user is onboarded
    is_onboarded = user.get("is_onboarded", False)
    
    # Get next parameter from state (passed through OAuth flow)
    next_param = request.query_params.get("state") or request.query_params.get("next", "/setup" if not is_onboarded else "/dashboard")
    
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    # Ensure next_param starts with /
    if not next_param.startswith("/"):
        next_param = "/" + next_param
    redirect_target = f"{frontend_url}{next_param}"

    response = RedirectResponse(url=redirect_target)
    await _start_session(response, request, database, user_id)
    return response

def _current_session_id(request: Request) -> Optional[str]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        return verify_access_claims(token).get("sid")
    except Exception:
        return None


@auth_routes.get("/sessions")
async def list_sessions(
    request: Request,
    current_user: dict = Depends(require_signed_in),
    db=Depends(get_database),
):
    """Devices signed in to this account. The current one is marked."""
    current = _current_session_id(request)
    docs = await db[SESSIONS].find(
        {"user_id": current_user["user_id"], "revoked_at": None},
        {"_id": 0, "session_id": 1, "user_agent": 1, "created_at": 1, "last_used_at": 1},
    ).sort("last_used_at", -1).to_list(length=50)
    return {"sessions": [{**d, "current": d["session_id"] == current} for d in docs]}


@auth_routes.delete("/sessions/{session_id}")
async def sign_out_device(
    session_id: str,
    current_user: dict = Depends(require_signed_in),
    db=Depends(get_database),
):
    """Signs out one device. Only this account's own sessions can be ended."""
    session = await db[SESSIONS].find_one({"session_id": session_id, "user_id": current_user["user_id"]}, {"revoked_at": 1})
    if session is None or session.get("revoked_at") is not None:
        raise HTTPException(status_code=404, detail="That device isn't signed in.")
    await revoke_session(db, session_id, reason="signed_out_device")
    return {"status": "signed_out"}


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


@auth_routes.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: dict = Depends(require_signed_in),
    db=Depends(get_database),
):
    """Changes the password and signs out every other device. This device stays signed in."""
    user = await db["users"].find_one({"user_id": current_user["user_id"]}, {"password": 1, "email": 1})
    if not user or not bcrypt.checkpw(payload.current_password.encode("utf-8"), user["password"].encode("utf-8")):
        raise HTTPException(status_code=400, detail="Your current password isn't right.")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=400, detail="Choose a different password.")

    new_hash = bcrypt.hashpw(payload.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    now = datetime.now(timezone.utc)
    await db["users"].update_one({"user_id": current_user["user_id"]}, {"$set": {"password": new_hash, "updated_at": now}})
    await revoke_all(db, current_user["user_id"], except_session_id=_current_session_id(request), reason="password_changed")
    if user.get("email"):
        mail.password_changed(user["email"], current_user["user_id"], now)
    return {"status": "success", "message": "Password changed. Other devices were signed out."}
