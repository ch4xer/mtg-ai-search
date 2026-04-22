"""Admin settings workflows."""

from fastapi import HTTPException

from ..config import get_rate_limits, update_rate_limits
from ..repositories.admin import persist_rate_limit_settings
from ..schemas.admin import UpdateSettingsRequest


async def get_settings() -> dict:
    limits = get_rate_limits()
    return {
        "anon_hourly_limit": limits["anon_hourly"],
        "user_hourly_limit": limits["user_hourly"],
    }


async def update_settings(req: UpdateSettingsRequest) -> dict:
    if req.anon_hourly_limit is not None and req.anon_hourly_limit < 0:
        raise HTTPException(status_code=400, detail="匿名用户限制不能为负数")
    if req.user_hourly_limit is not None and req.user_hourly_limit < 0:
        raise HTTPException(status_code=400, detail="注册用户限制不能为负数")

    limits = update_rate_limits(
        anon_hourly=req.anon_hourly_limit,
        user_hourly=req.user_hourly_limit,
    )
    await persist_rate_limit_settings(req.anon_hourly_limit, req.user_hourly_limit)

    return {
        "anon_hourly_limit": limits["anon_hourly"],
        "user_hourly_limit": limits["user_hourly"],
    }

