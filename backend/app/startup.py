import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI

from .auth import hash_password
from .config import get_admin_credentials
from .db import close_pool, get_pool
from .maintenance import backfill_missing_embeddings, incremental_sync, seed_cards_if_empty
from .migrations import run_cards_migrations, run_post_seed, run_pre_seed

logger = logging.getLogger(__name__)


async def ensure_admin_account(pool) -> None:
    """Create or promote the built-in admin account configured in env vars."""
    admin_user, admin_password = get_admin_credentials()
    if not admin_user or not admin_password:
        return

    existing_user = await pool.fetchrow(
        "SELECT id FROM users WHERE username = $1",
        admin_user,
    )
    if existing_user:
        await pool.execute(
            "UPDATE users SET role = 'admin' WHERE username = $1",
            admin_user,
        )
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool = await get_pool()

    await run_pre_seed(pool)
    await ensure_admin_account(pool)
    await seed_cards_if_empty()
    await run_cards_migrations(pool)
    await run_post_seed(pool)
    await backfill_missing_embeddings()

    sync_task = asyncio.create_task(_daily_sync_loop())

    yield

    sync_task.cancel()
    await close_pool()
