import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI

from .auth import hash_password, verify_password
from .config import get_admin_credentials, update_rate_limits
from .db import close_pool, get_pool
from .maintenance import (
    backfill_missing_embeddings,
    incremental_sync,
    seed_abilities_if_empty,
    seed_cards_if_empty,
)
from .migrations import run_cards_migrations, run_post_seed, run_pre_seed

logger = logging.getLogger(__name__)


async def ensure_admin_account(pool) -> None:
    """Create or promote the built-in admin account configured in env vars.

    If the account already exists and the env password differs from the stored
    hash, the password is updated so that operators can rotate credentials by
    changing the environment variable.
    """
    admin_user, admin_password = get_admin_credentials()
    if not admin_user or not admin_password:
        return

    existing_user = await pool.fetchrow(
        "SELECT id, password_hash FROM users WHERE username = $1",
        admin_user,
    )
    if existing_user:
        await pool.execute(
            "UPDATE users SET role = 'admin' WHERE username = $1",
            admin_user,
        )
        # Update password if it changed in the environment
        if not verify_password(admin_password, existing_user["password_hash"]):
            await pool.execute(
                "UPDATE users SET password_hash = $1 WHERE username = $2",
                hash_password(admin_password),
                admin_user,
            )
            logger.info("Admin account '%s' password updated from environment.", admin_user)
        return

    await pool.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ($1, $2, 'admin')",
        admin_user,
        hash_password(admin_password),
    )
    logger.info("Built-in admin account '%s' created.", admin_user)


CST = timezone(timedelta(hours=8))


def _seconds_until_midnight() -> float:
    """Return seconds from now until midnight CST (00:00)."""
    now = datetime.now(CST)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (tomorrow - now).total_seconds()


async def _daily_sync_loop():
    """Background loop: sleep until midnight CST, then check for new cards."""
    while True:
        delay = _seconds_until_midnight()
        logger.info("[scheduler] Next sync check in %.0f seconds (midnight CST).", delay)
        await asyncio.sleep(delay)
        try:
            result = await incremental_sync()
            if result["skipped"]:
                logger.info("[scheduler] No updates from Scryfall.")
            else:
                logger.info("[scheduler] Synced %d new cards.", result["new_cards"])
        except Exception:
            logger.exception("[scheduler] Sync failed")


async def _load_persisted_settings(pool) -> None:
    """Load rate-limit settings from app_meta into in-memory config."""
    rows = await pool.fetch(
        "SELECT key, value FROM app_meta WHERE key IN ('anon_hourly_limit', 'user_hourly_limit')"
    )
    kwargs = {}
    for row in rows:
        try:
            val = int(row["value"])
        except (ValueError, TypeError):
            continue
        if row["key"] == "anon_hourly_limit":
            kwargs["anon_hourly"] = val
        elif row["key"] == "user_hourly_limit":
            kwargs["user_hourly"] = val
    if kwargs:
        update_rate_limits(**kwargs)
        logger.info("Loaded persisted rate limits: %s", kwargs)


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool = await get_pool()

    await run_pre_seed(pool)
    await ensure_admin_account(pool)
    await seed_cards_if_empty()
    await seed_abilities_if_empty()
    await run_cards_migrations(pool)
    await run_post_seed(pool)
    await _load_persisted_settings(pool)
    await backfill_missing_embeddings()

    sync_task = asyncio.create_task(_daily_sync_loop())

    yield

    sync_task.cancel()
    await close_pool()
