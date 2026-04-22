from fastapi import HTTPException

from ..repositories.users import get_user_by_id, verify_user_email
from ..schemas.auth import VerifyEmailRequest
from .auth_helpers import issue_verification_code


async def verify_email_code(user_id: str, req: VerifyEmailRequest) -> dict:
    result = await verify_user_email(user_id, req.code)
    if result == "too_many_attempts":
        raise HTTPException(status_code=429, detail="Too many failed attempts, please request a new code")
    if result == "invalid":
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    return {"message": "Email verified successfully"}


async def resend_verification_code(user_id: str) -> dict:
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email already verified")
    if not user.get("email"):
        raise HTTPException(status_code=400, detail="No email address on file")

    if not await issue_verification_code(user_id, user["email"]):
        raise HTTPException(status_code=500, detail="Failed to send verification email")
    return {"message": "Verification code sent"}
