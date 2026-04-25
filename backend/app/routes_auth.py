"""Auth endpoints: register, login, refresh, me, email verification, password change."""

from fastapi import APIRouter, Depends

from .auth import get_current_user
from .schemas.auth import (
    ApiKeyCreateResponse,
    ApiKeyStatusResponse,
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    VerifyEmailRequest,
)
from .services.api_key_service import get_user_api_key_status, regenerate_user_api_key
from .services.auth_email_service import resend_verification_code, verify_email_code
from .services.auth_password_service import change_user_password, request_password_change_code
from .services.auth_session_service import get_current_profile, login_user, refresh_access_token, register_user

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


@auth_router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    return AuthResponse(**await register_user(req))


@auth_router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    return AuthResponse(**await login_user(req))


@auth_router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest, user_id: str = Depends(get_current_user)):
    return await verify_email_code(user_id, req)


@auth_router.post("/resend-verification")
async def resend_verification(user_id: str = Depends(get_current_user)):
    return await resend_verification_code(user_id)


@auth_router.post("/refresh")
async def refresh(req: RefreshRequest):
    return refresh_access_token(req.refresh_token)


@auth_router.get("/me")
async def me(user_id: str = Depends(get_current_user)):
    """Return the current user's profile, refreshed from the database."""
    return await get_current_profile(user_id)


@auth_router.get("/api-key", response_model=ApiKeyStatusResponse)
async def api_key_status(user_id: str = Depends(get_current_user)):
    return ApiKeyStatusResponse(**await get_user_api_key_status(user_id))


@auth_router.post("/api-key", response_model=ApiKeyCreateResponse)
async def regenerate_api_key(user_id: str = Depends(get_current_user)):
    return ApiKeyCreateResponse(**await regenerate_user_api_key(user_id))


@auth_router.post("/request-password-change")
async def request_password_change(user_id: str = Depends(get_current_user)):
    """Send a verification code to the user's email for password change."""
    return await request_password_change_code(user_id)


@auth_router.post("/change-password")
async def change_password(req: ChangePasswordRequest, user_id: str = Depends(get_current_user)):
    """Change password after verifying the email code."""
    return await change_user_password(user_id, req)
