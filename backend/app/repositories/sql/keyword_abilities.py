from .connection import get_pool

async def get_all_keywords() -> list[str]:
    """Return all keyword ability names from the database."""
    pool = await get_pool()
    rows = await pool.fetch("SELECT name FROM keyword_abilities ORDER BY name")
    return [row["name"] for row in rows]

