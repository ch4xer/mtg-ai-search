"""Auth endpoints: register, login, refresh, me, email verification."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from .auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from .db import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    set_verification_code,
    verify_user_email,
)
from .email import generate_verification_code, send_verification_email

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])

VERIFICATION_CODE_EXPIRY_MINUTES = 10


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    code: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


@auth_router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    if len(req.username) < 2:
        raise HTTPException(status_code=400, detail="Username must be at least 2 characters")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    existing = await get_user_by_username(req.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    email = req.email.lower()
    existing_email = await get_user_by_email(email)
    if existing_email:
        raise HTTPException(status_code=409, detail="Email already registered")

    pw_hash = hash_password(req.password)
    user = await create_user(req.username, pw_hash, email=email, email_verified=False)

    # Generate and send verification code
    code = generate_verification_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES)
    await set_verification_code(user["id"], code, expires_at)
    send_verification_email(email, code)

    return AuthResponse(
        access_token=create_access_token(user["id"]),
        refresh_token=create_refresh_token(user["id"]),
        user=user,
    )


@auth_router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    user = await get_user_by_username(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    user_info = {
        "id": user["id"], "username": user["username"], "role": user["role"],
        "email": user["email"], "email_verified": user["email_verified"],
    }
    return AuthResponse(
        access_token=create_access_token(user["id"]),
        refresh_token=create_refresh_token(user["id"]),
        user=user_info,
    )


@auth_router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest, user_id: str = Depends(get_current_user)):
    result = await verify_user_email(user_id, req.code)
    if result == "too_many_attempts":
        raise HTTPException(status_code=429, detail="Too many failed attempts, please request a new code")
    if result == "invalid":
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    return {"message": "Email verified successfully"}


@auth_router.post("/resend-verification")
async def resend_verification(user_id: str = Depends(get_current_user)):
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email already verified")
    if not user.get("email"):
        raise HTTPException(status_code=400, detail="No email address on file")

    code = generate_verification_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES)
    await set_verification_code(user_id, code, expires_at)
    sent = send_verification_email(user["email"], code)
    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send verification email")
    return {"message": "Verification code sent"}


@auth_router.post("/refresh")
async def refresh(req: RefreshRequest):
    user_id = decode_token(req.refresh_token, expected_type="refresh")
    return {"access_token": create_access_token(user_id)}


@auth_router.get("/me")
async def me(user_id: str = Depends(get_current_user)):
    """Return the current user's profile, refreshed from the database."""
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user["id"], "username": user["username"], "role": user["role"],
        "email": user.get("email"), "email_verified": user.get("email_verified", False),
    }
