import logging
import os

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
DEFAULT_DATABASE_URL = "postgresql://mtg:mtg_password@localhost:5432/mtg"

async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        dsn = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
        _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
        logger.info("Created asyncpg connection pool")
    return _pool

async def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Closed asyncpg connection pool")
