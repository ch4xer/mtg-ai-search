"""Facet queries for card discovery."""

from .helpers import _MAIN_TYPES


async def get_discovery_facets(pool, where: str, params: list, need_rarity_join: bool) -> dict:
    color_facets = await _get_color_facets(pool, where, params, need_rarity_join)
    rarity_facets = await _get_rarity_facets(pool, where, params)
    type_facets = await _get_type_facets(pool, where, params, need_rarity_join)
    keyword_facets = await _get_keyword_facets(pool, where, params, need_rarity_join)
    subtype_facets = await _get_subtype_facets(pool, where, params, need_rarity_join)
    range_facets = await _get_range_facets(pool, where, params, need_rarity_join)

    return {
        "colors": color_facets,
        "types": type_facets,
        "rarities": rarity_facets,
        "keywords": keyword_facets,
        "subtypes": subtype_facets,
        **range_facets,
    }


async def _get_color_facets(pool, where: str, params: list, need_rarity_join: bool) -> dict:
    if need_rarity_join:
        rows = await pool.fetch(
            f"SELECT c AS val, COUNT(*) AS cnt FROM cards c LEFT JOIN card_prints cp ON cp.card_id = c.id, unnest(colors) AS c WHERE {where} GROUP BY c ORDER BY cnt DESC",
            *params,
        )
    else:
        rows = await pool.fetch(
            f"SELECT c AS val, COUNT(*) AS cnt FROM cards, unnest(colors) AS c WHERE {where} GROUP BY c ORDER BY cnt DESC",
            *params,
        )
    return {r["val"]: int(r["cnt"]) for r in rows}


async def _get_rarity_facets(pool, where: str, params: list) -> dict:
    rows = await pool.fetch(
        f"SELECT cp.rarity AS val, COUNT(*) AS cnt FROM cards c LEFT JOIN card_prints cp ON cp.card_id = c.id WHERE {where} AND cp.rarity IS NOT NULL GROUP BY val ORDER BY cnt DESC",
        *params,
    )
    return {r["val"]: int(r["cnt"]) for r in rows}


async def _get_type_facets(pool, where: str, params: list, need_rarity_join: bool) -> dict:
    type_cases = ", ".join(
        f"COUNT(*) FILTER (WHERE type_line ILIKE '%%{card_type}%%') AS \"{card_type}\""
        for card_type in _MAIN_TYPES
    )
    if need_rarity_join:
        row = await pool.fetchrow(
            f"SELECT {type_cases} FROM cards c LEFT JOIN card_prints cp ON cp.card_id = c.id WHERE {where}",
            *params,
        )
    else:
        row = await pool.fetchrow(f"SELECT {type_cases} FROM cards WHERE {where}", *params)
    return {card_type: int(row[card_type]) for card_type in _MAIN_TYPES if row[card_type]}


async def _get_keyword_facets(pool, where: str, params: list, need_rarity_join: bool) -> list[dict]:
    if need_rarity_join:
        rows = await pool.fetch(
            f"SELECT k AS val, COUNT(*) AS cnt FROM cards c LEFT JOIN card_prints cp ON cp.card_id = c.id, unnest(keywords) AS k WHERE {where} GROUP BY k ORDER BY cnt DESC LIMIT 30",
            *params,
        )
    else:
        rows = await pool.fetch(
            f"SELECT k AS val, COUNT(*) AS cnt FROM cards, unnest(keywords) AS k WHERE {where} GROUP BY k ORDER BY cnt DESC LIMIT 30",
            *params,
        )
    return [{"name": r["val"], "count": int(r["cnt"])} for r in rows]


async def _get_subtype_facets(pool, where: str, params: list, need_rarity_join: bool) -> list[dict]:
    if need_rarity_join:
        rows = await pool.fetch(
            f"""SELECT s AS val, COUNT(*) AS cnt
                FROM (
                    SELECT unnest(string_to_array(
                        trim(split_part(type_line, '\u2014', 2)), ' '
                    )) AS s
                    FROM cards c LEFT JOIN card_prints cp ON cp.card_id = c.id
                    WHERE {where} AND type_line LIKE '%%\u2014%%'
                ) sub
                WHERE s != ''
                GROUP BY s ORDER BY cnt DESC LIMIT 40""",
            *params,
        )
    else:
        rows = await pool.fetch(
            f"""SELECT s AS val, COUNT(*) AS cnt
                FROM (
                    SELECT unnest(string_to_array(
                        trim(split_part(type_line, '\u2014', 2)), ' '
                    )) AS s
                    FROM cards
                    WHERE {where} AND type_line LIKE '%%\u2014%%'
                ) sub
                WHERE s != ''
                GROUP BY s ORDER BY cnt DESC LIMIT 40""",
            *params,
        )
    return [{"name": r["val"], "count": int(r["cnt"])} for r in rows]


async def _get_range_facets(pool, where: str, params: list, need_rarity_join: bool) -> dict:
    if need_rarity_join:
        row = await pool.fetchrow(
            f"""SELECT
                    MIN(cmc) AS cmc_min, MAX(cmc) AS cmc_max,
                    MIN(CAST(power AS real)) FILTER (WHERE power ~ '^[0-9]+\\.?[0-9]*$') AS power_min,
                    MAX(CAST(power AS real)) FILTER (WHERE power ~ '^[0-9]+\\.?[0-9]*$') AS power_max,
                    MIN(CAST(toughness AS real)) FILTER (WHERE toughness ~ '^[0-9]+\\.?[0-9]*$') AS toughness_min,
                    MAX(CAST(toughness AS real)) FILTER (WHERE toughness ~ '^[0-9]+\\.?[0-9]*$') AS toughness_max
                FROM cards c LEFT JOIN card_prints cp ON cp.card_id = c.id WHERE {where}""",
            *params,
        )
    else:
        row = await pool.fetchrow(
            f"""SELECT
                    MIN(cmc) AS cmc_min, MAX(cmc) AS cmc_max,
                    MIN(CAST(power AS real)) FILTER (WHERE power ~ '^[0-9]+\\.?[0-9]*$') AS power_min,
                    MAX(CAST(power AS real)) FILTER (WHERE power ~ '^[0-9]+\\.?[0-9]*$') AS power_max,
                    MIN(CAST(toughness AS real)) FILTER (WHERE toughness ~ '^[0-9]+\\.?[0-9]*$') AS toughness_min,
                    MAX(CAST(toughness AS real)) FILTER (WHERE toughness ~ '^[0-9]+\\.?[0-9]*$') AS toughness_max
                FROM cards WHERE {where}""",
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

