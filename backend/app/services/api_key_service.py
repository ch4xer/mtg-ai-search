import asyncio
import hashlib
import logging
import secrets

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

from ..repositories.users import get_api_key_status, get_user_by_api_key_hash, set_user_api_key, update_last_active

API_KEY_PREFIX = "mtg_"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


async def get_user_api_key_status(user_id: str) -> dict:
    status_data = await get_api_key_status(user_id)
    if status_data is None:
        raise HTTPException(status_code=404, detail="User not found")
    return status_data


async def regenerate_user_api_key(user_id: str) -> dict:
    api_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    status_data = await set_user_api_key(user_id, hash_api_key(api_key))
    if status_data is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "api_key": api_key,
        "created_at": status_data["created_at"],
    }


async def authenticate_api_key(api_key: str) -> dict:
    key = (api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    user = await get_user_by_api_key_hash(hash_api_key(key))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    task = asyncio.create_task(update_last_active(user["id"]))
    task.add_done_callback(_log_last_active_error)
    return user


def _log_last_active_error(task: asyncio.Task) -> None:
    exc = task.exception()
    if exc:
        logger.warning("update_last_active failed: %s", exc)
