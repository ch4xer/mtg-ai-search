from fastapi import HTTPException

from ..auth import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from ..repositories.users import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    update_last_active,
)
from ..schemas.auth import LoginRequest, RegisterRequest
from .auth_helpers import issue_verification_code, public_user


async def register_user(req: RegisterRequest) -> dict:
    if len(req.username) < 2:
        raise HTTPException(status_code=400, detail="Username must be at least 2 characters")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if await get_user_by_username(req.username):
        raise HTTPException(status_code=409, detail="Username already taken")

    email = req.email.lower()
    if await get_user_by_email(email):
        raise HTTPException(status_code=409, detail="Email already registered")

    user = await create_user(req.username, hash_password(req.password), email=email, email_verified=False)
    await issue_verification_code(user["id"], email)

    return {
        "access_token": create_access_token(user["id"]),
        "refresh_token": create_refresh_token(user["id"]),
        "user": user,
    }


async def login_user(req: LoginRequest) -> dict:
    user = await get_user_by_username(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    await update_last_active(user["id"])
    return {
        "access_token": create_access_token(user["id"]),
        "refresh_token": create_refresh_token(user["id"]),
        "user": public_user(user),
    }


def refresh_access_token(refresh_token: str) -> dict:
    user_id = decode_token(refresh_token, expected_type="refresh")
    return {"access_token": create_access_token(user_id)}


async def get_current_profile(user_id: str) -> dict:
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await update_last_active(user_id)
    return public_user(user)
