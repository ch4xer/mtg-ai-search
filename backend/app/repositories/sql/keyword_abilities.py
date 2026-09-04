from .connection import get_pool

async def get_all_keywords() -> list[str]:
    """Return all keyword ability names from the database."""
    pool = await get_pool()
    rows = await pool.fetch("SELECT name FROM keyword_abilities ORDER BY name")
    return [row["name"] for row in rows]


async def get_keyword_ability_rows() -> list[dict]:
    """Return stored bilingual keyword metadata.

    Reading optional fields through ``to_jsonb`` keeps this query compatible
    while an existing installation is waiting for its startup migration.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT ka.name,
                  ka.description,
                  COALESCE(to_jsonb(ka) ->> 'name_zh', '') AS name_zh,
                  COALESCE(to_jsonb(ka) ->> 'description_zh', '') AS description_zh
           FROM keyword_abilities ka
           ORDER BY ka.name"""
    )
    return [dict(row) for row in rows]
