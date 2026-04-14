"""Auth endpoints: register, login, refresh, me."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from .db import create_user, get_user_by_id, get_user_by_username

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


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
    pw_hash = hash_password(req.password)
    user = await create_user(req.username, pw_hash)
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
    user_info = {"id": user["id"], "username": user["username"], "role": user["role"]}
    return AuthResponse(
        access_token=create_access_token(user["id"]),
        refresh_token=create_refresh_token(user["id"]),
        user=user_info,
    )


@auth_router.post("/refresh")
async def refresh(req: RefreshRequest):
    user_id = decode_token(req.refresh_token, expected_type="refresh")
    return {"access_token": create_access_token(user_id)}


@auth_router.get("/me")
async def me(user_id: str = Depends(get_current_user)):
    """Return the current user's profile, refreshed from the database.

    Used by the frontend to pick up role changes without requiring re-login.
    """
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user["id"], "username": user["username"], "role": user["role"]}
