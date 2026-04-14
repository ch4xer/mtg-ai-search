from fastapi import Request

from .auth import decode_token


async def get_optional_user(request: Request) -> str | None:
    """Extract user_id from a Bearer token when present."""
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None

    try:
        return decode_token(authorization[7:], expected_type="access")
    except Exception:
        return None
