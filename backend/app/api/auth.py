from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


@router.get("/google")
async def google_login(passphrase: str = Query(...)):
    """Initiate Google OAuth with passphrase embedded in state."""
    import urllib.parse
    import base64
    import json

    settings = get_settings()
    # Validate passphrase before redirecting
    if passphrase != settings.invite_passphrase:
        raise HTTPException(status_code=403, detail="Invalid invite passphrase")

    state = base64.urlsafe_b64encode(json.dumps({"passphrase": passphrase}).encode()).decode()

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=url)


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Exchange OAuth code, validate passphrase, upsert user, return JWT."""
    import base64
    import json

    # Decode and validate state/passphrase
    try:
        state_data = json.loads(base64.urlsafe_b64decode(state).decode())
        passphrase = state_data.get("passphrase", "")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    settings = get_settings()
    if passphrase != settings.invite_passphrase:
        raise HTTPException(status_code=403, detail="Invalid invite passphrase")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange OAuth code")
        token_data = token_resp.json()

        # Get user info
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        userinfo = userinfo_resp.json()

    # Upsert user
    result = await db.execute(select(User).where(User.google_id == userinfo["sub"]))
    user = result.scalar_one_or_none()

    from datetime import datetime, timezone, timedelta
    token_expiry = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))

    if not user:
        user = User(
            google_id=userinfo["sub"],
            email=userinfo["email"],
            name=userinfo.get("name", userinfo["email"]),
            avatar_url=userinfo.get("picture"),
            google_access_token=token_data["access_token"],
            google_refresh_token=token_data.get("refresh_token"),
            google_token_expiry=token_expiry,
        )
        db.add(user)
    else:
        user.google_access_token = token_data["access_token"]
        if token_data.get("refresh_token"):
            user.google_refresh_token = token_data["refresh_token"]
        user.google_token_expiry = token_expiry
        user.avatar_url = userinfo.get("picture")

    await db.flush()
    await db.refresh(user)

    access_token = create_access_token(str(user.id))

    # Redirect to frontend with token
    redirect_url = f"{settings.frontend_url}/auth/callback?token={access_token}"
    return RedirectResponse(url=redirect_url)


@router.get("/me", response_model=UserOut)
async def get_me(
    user_id: str = Depends(__import__("app.core.security", fromlist=["get_current_user_id"]).get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
