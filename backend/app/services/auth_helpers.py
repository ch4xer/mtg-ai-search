from datetime import datetime, timedelta, timezone

from ..email import generate_verification_code, send_verification_email
from ..repositories.users import set_verification_code

VERIFICATION_CODE_EXPIRY_MINUTES = 10


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "email": user.get("email"),
        "email_verified": user.get("email_verified", False),
    }


async def issue_verification_code(user_id: str, email: str) -> bool:
    code = generate_verification_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES)
    await set_verification_code(user_id, code, expires_at)
    return send_verification_email(email, code)
