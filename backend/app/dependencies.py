from fastapi import HTTPException, Request, status

from .auth import decode_token


async def get_optional_user(request: Request) -> str | None:
    """Extract user_id from a Bearer token when present.

    Returns None only when no token is provided (truly anonymous).
    Raises 401 when a token IS provided but is invalid/expired,
    so the frontend can trigger its token-refresh flow.
    """
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None

    # Token was provided — if it's bad, tell the client instead of
    # silently downgrading to anonymous.
    return decode_token(authorization[7:], expected_type="access")
