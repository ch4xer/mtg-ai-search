"""Card discovery SQL orchestration."""

from .card_discovery_facets import get_discovery_facets
from .card_discovery_filters import build_discovery_filter
from .card_result_rows import CARD_RESULT_COLUMNS, DEFAULT_PRINT_JOIN, serialize_card_result
from .connection import get_pool


async def discover_cards(
    q: str = "",
    colors: list[str] | None = None,
    types: list[str] | None = None,
    rarities: list[str] | None = None,
    keywords: list[str] | None = None,
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    power_min: float | None = None,
    power_max: float | None = None,
    subtypes: list[str] | None = None,
    toughness_min: float | None = None,
    toughness_max: float | None = None,
    include_playtest: bool = False,
    page: int = 1,
    page_size: int = 60,
) -> dict:
    """Discover cards with full-text keyword search, faceted filters, and pagination."""
    pool = await get_pool()
    filter_spec = build_discovery_filter(
        q=q,
        colors=colors,
        types=types,
        rarities=rarities,
        keywords=keywords,
        cmc_min=cmc_min,
        cmc_max=cmc_max,
        power_min=power_min,
        power_max=power_max,
        subtypes=subtypes,
        toughness_min=toughness_min,
        toughness_max=toughness_max,
    )

    total = await _count_discovery_results(pool, filter_spec.where, filter_spec.params, filter_spec.need_rarity_join)
    rows = await _fetch_discovery_page(pool, filter_spec, page, page_size)
    cards = [serialize_card_result(row) for row in rows]
    facets = await get_discovery_facets(
        pool,
        filter_spec.where,
        filter_spec.params,
        filter_spec.need_rarity_join,
    )

    return {
        "results": cards,
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "facets": facets,
    }


async def _count_discovery_results(pool, where: str, params: list, need_rarity_join: bool) -> int:
    if need_rarity_join:
        return await pool.fetchval(
            f"SELECT COUNT(*) FROM (SELECT DISTINCT ON (c.name) c.id FROM cards c LEFT JOIN card_prints cp ON cp.card_id = c.id WHERE {where} ORDER BY c.name) sub",
            *params,
        )
    return await pool.fetchval(
        f"SELECT COUNT(*) FROM (SELECT DISTINCT ON (name) id FROM cards WHERE {where} ORDER BY name) sub",
        *params,
    )


async def _fetch_discovery_page(pool, filter_spec, page: int, page_size: int):
    offset = (page - 1) * page_size
    limit_idx = filter_spec.next_param_index
    offset_idx = filter_spec.next_param_index + 1

    if filter_spec.need_rarity_join:
        return await pool.fetch(
            f"""SELECT {CARD_RESULT_COLUMNS}
                FROM (
                  SELECT DISTINCT ON (c.name) c.id, c.name
                  FROM cards c LEFT JOIN card_prints cp ON cp.card_id = c.id
                  WHERE {filter_spec.where}
                  ORDER BY c.name
                ) sub
                JOIN cards c ON c.id = sub.id
                {DEFAULT_PRINT_JOIN}
                ORDER BY c.name
                LIMIT ${limit_idx} OFFSET ${offset_idx}""",
            *filter_spec.params,
            page_size,
            offset,
        )

    return await pool.fetch(
        f"""SELECT {CARD_RESULT_COLUMNS}
            FROM (
              SELECT DISTINCT ON (name) id, name
              FROM cards WHERE {filter_spec.where}
              ORDER BY name
            ) sub
            JOIN cards c ON c.id = sub.id
            {DEFAULT_PRINT_JOIN}
            ORDER BY c.name
            LIMIT ${limit_idx} OFFSET ${offset_idx}""",
        *filter_spec.params,
        page_size,
        offset,
    )
