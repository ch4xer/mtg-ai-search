from fastapi import HTTPException

from ..auth import hash_password
from ..repositories.users import get_user_by_id, update_user_password, verify_user_email
from ..schemas.auth import ChangePasswordRequest
from .auth_helpers import issue_verification_code


async def request_password_change_code(user_id: str) -> dict:
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.get("email"):
        raise HTTPException(status_code=400, detail="No email address on file")

    if not await issue_verification_code(user_id, user["email"]):
        raise HTTPException(status_code=500, detail="Failed to send verification email")
    return {"message": "Verification code sent to your email"}


async def change_user_password(user_id: str, req: ChangePasswordRequest) -> dict:
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    result = await verify_user_email(user_id, req.code)
    if result == "too_many_attempts":
        raise HTTPException(status_code=429, detail="Too many failed attempts, please request a new code")
    if result == "invalid":
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    await update_user_password(user_id, hash_password(req.new_password))
    return {"message": "Password changed successfully"}
