"""Facet queries for card discovery."""

from .helpers import _MAIN_TYPES


async def get_discovery_facets(pool, where: str, params: list, need_print_join: bool) -> dict:
    color_facets = await _get_color_facets(pool, where, params, need_print_join)
    rarity_facets = await _get_rarity_facets(pool, where, params)
    type_facets = await _get_type_facets(pool, where, params, need_print_join)
    keyword_facets = await _get_keyword_facets(pool, where, params, need_print_join)
    subtype_facets = await _get_subtype_facets(pool, where, params, need_print_join)
    range_facets = await _get_range_facets(pool, where, params, need_print_join)

    return {
        "colors": color_facets,
        "types": type_facets,
        "rarities": rarity_facets,
        "keywords": keyword_facets,
        "subtypes": subtype_facets,
        **range_facets,
    }


async def _get_color_facets(pool, where: str, params: list, need_print_join: bool) -> dict:
    if need_print_join:
        rows = await pool.fetch(
            f"SELECT color_val AS val, COUNT(DISTINCT c.id) AS cnt FROM cards c JOIN card_prints cp ON cp.card_id = c.id, unnest(c.colors) AS color_val WHERE {where} GROUP BY color_val ORDER BY cnt DESC",
            *params,
        )
    else:
        rows = await pool.fetch(
            f"SELECT color_val AS val, COUNT(DISTINCT c.id) AS cnt FROM cards c, unnest(c.colors) AS color_val WHERE {where} GROUP BY color_val ORDER BY cnt DESC",
            *params,
        )
    return {r["val"]: int(r["cnt"]) for r in rows}


async def _get_rarity_facets(pool, where: str, params: list) -> dict:
    rows = await pool.fetch(
        f"SELECT cp.rarity AS val, COUNT(DISTINCT c.id) AS cnt FROM cards c JOIN card_prints cp ON cp.card_id = c.id WHERE {where} AND cp.rarity IS NOT NULL GROUP BY val ORDER BY cnt DESC",
        *params,
    )
    return {r["val"]: int(r["cnt"]) for r in rows}


async def _get_type_facets(pool, where: str, params: list, need_print_join: bool) -> dict:
    type_cases = ", ".join(
        f"COUNT(DISTINCT c.id) FILTER (WHERE c.type_line ILIKE '%%{card_type}%%') AS \"{card_type}\""
        for card_type in _MAIN_TYPES
    )
    if need_print_join:
        row = await pool.fetchrow(
            f"SELECT {type_cases} FROM cards c JOIN card_prints cp ON cp.card_id = c.id WHERE {where}",
            *params,
        )
    else:
        row = await pool.fetchrow(f"SELECT {type_cases} FROM cards c WHERE {where}", *params)
    return {card_type: int(row[card_type]) for card_type in _MAIN_TYPES if row[card_type]}


async def _get_keyword_facets(pool, where: str, params: list, need_print_join: bool) -> list[dict]:
    if need_print_join:
        rows = await pool.fetch(
            f"SELECT k AS val, COUNT(DISTINCT c.id) AS cnt FROM cards c JOIN card_prints cp ON cp.card_id = c.id, unnest(c.keywords) AS k WHERE {where} GROUP BY k ORDER BY cnt DESC LIMIT 30",
            *params,
        )
    else:
        rows = await pool.fetch(
            f"SELECT k AS val, COUNT(DISTINCT c.id) AS cnt FROM cards c, unnest(c.keywords) AS k WHERE {where} GROUP BY k ORDER BY cnt DESC LIMIT 30",
            *params,
        )
    return [{"name": r["val"], "count": int(r["cnt"])} for r in rows]


async def _get_subtype_facets(pool, where: str, params: list, need_print_join: bool) -> list[dict]:
    if need_print_join:
        rows = await pool.fetch(
            f"""SELECT s AS val, COUNT(DISTINCT c.id) AS cnt
                FROM cards c
                JOIN card_prints cp ON cp.card_id = c.id,
                unnest(string_to_array(trim(split_part(c.type_line, '\u2014', 2)), ' ')) AS s
                WHERE {where} AND c.type_line LIKE '%%\u2014%%' AND s != ''
                GROUP BY s ORDER BY cnt DESC LIMIT 40""",
            *params,
        )
    else:
        rows = await pool.fetch(
            f"""SELECT s AS val, COUNT(DISTINCT c.id) AS cnt
                FROM cards c,
                unnest(string_to_array(trim(split_part(c.type_line, '\u2014', 2)), ' ')) AS s
                WHERE {where} AND c.type_line LIKE '%%\u2014%%' AND s != ''
                GROUP BY s ORDER BY cnt DESC LIMIT 40""",
            *params,
        )
    return [{"name": r["val"], "count": int(r["cnt"])} for r in rows]


async def _get_range_facets(pool, where: str, params: list, need_print_join: bool) -> dict:
    if need_print_join:
        row = await pool.fetchrow(
            f"""SELECT
                    MIN(c.cmc) AS cmc_min, MAX(c.cmc) AS cmc_max,
                    MIN(CAST(c.power AS real)) FILTER (WHERE c.power ~ '^[0-9]+\\.?[0-9]*$') AS power_min,
                    MAX(CAST(c.power AS real)) FILTER (WHERE c.power ~ '^[0-9]+\\.?[0-9]*$') AS power_max,
                    MIN(CAST(c.toughness AS real)) FILTER (WHERE c.toughness ~ '^[0-9]+\\.?[0-9]*$') AS toughness_min,
                    MAX(CAST(c.toughness AS real)) FILTER (WHERE c.toughness ~ '^[0-9]+\\.?[0-9]*$') AS toughness_max
                FROM cards c JOIN card_prints cp ON cp.card_id = c.id WHERE {where}""",
            *params,
        )
    else:
        row = await pool.fetchrow(
            f"""SELECT
                    MIN(c.cmc) AS cmc_min, MAX(c.cmc) AS cmc_max,
                    MIN(CAST(c.power AS real)) FILTER (WHERE c.power ~ '^[0-9]+\\.?[0-9]*$') AS power_min,
                    MAX(CAST(c.power AS real)) FILTER (WHERE c.power ~ '^[0-9]+\\.?[0-9]*$') AS power_max,
                    MIN(CAST(c.toughness AS real)) FILTER (WHERE c.toughness ~ '^[0-9]+\\.?[0-9]*$') AS toughness_min,
                    MAX(CAST(c.toughness AS real)) FILTER (WHERE c.toughness ~ '^[0-9]+\\.?[0-9]*$') AS toughness_max
                FROM cards c WHERE {where}""",
            *params,
        )

    return {
        "cmc_range": {
            "min": float(row["cmc_min"]) if row["cmc_min"] is not None else 0,
            "max": float(row["cmc_max"]) if row["cmc_max"] is not None else 0,
        },
        "power_range": {
            "min": float(row["power_min"]) if row["power_min"] is not None else 0,
            "max": float(row["power_max"]) if row["power_max"] is not None else 0,
        },
        "toughness_range": {
            "min": float(row["toughness_min"]) if row["toughness_min"] is not None else 0,
            "max": float(row["toughness_max"]) if row["toughness_max"] is not None else 0,
        },
    }
