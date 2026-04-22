"""Admin dashboard statistics."""

from ..repositories.admin import get_dashboard_stats


async def get_admin_stats() -> dict:
    return await get_dashboard_stats()

