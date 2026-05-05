"""Card search and discover workflows."""

import asyncio

from fastapi import HTTPException, Request

from ..config import get_rate_limits
from ..repositories.cards import discover_cards, get_all_keywords, get_card_prints_by_oracle_id
from ..repositories.search_logs import get_ip_hourly_search_count, get_user_hourly_search_count, log_search
from ..repositories.users import get_user_by_id
from ..schemas.search import DiscoverRequest
from .tag_search_service import search_tags


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def search_cards(
    query: str,
    client_ip: str,
    user_id: str | None,
    *,
    rerank_enabled: bool = True,
    rerank_top_n: int = 200,
) -> list[dict]:
    limits = get_rate_limits()
    anon_limit = limits["anon_hourly"]
    user_limit = limits["user_hourly"]

    if user_id:
        user = await get_user_by_id(user_id)
        if not user or user.get("role") != "admin":
            count = await get_user_hourly_search_count(user_id)
            if count >= user_limit:
                raise HTTPException(status_code=429, detail=f"搜索次数已达上限 ({user_limit}次/小时)")
    else:
        count = await get_ip_hourly_search_count(client_ip)
        if count >= anon_limit:
            raise HTTPException(
                status_code=429,
                detail=f"未登录用户搜索次数已达上限 ({anon_limit}次/小时)，请登录后使用",
            )

    search_result = await search_tags(query)
    asyncio.create_task(
        log_search(
            user_id,
            query,
            int(search_result.get("catalog", {}).get("card_filter_tokens_prompt") or 0),
            int(search_result.get("catalog", {}).get("card_filter_tokens_completion") or 0),
            ip_address=client_ip,
        )
    )
    return search_result["cards"]


async def discover(req: DiscoverRequest) -> dict:
    return await discover_cards(
        q=req.q,
        colors=req.colors,
        types=req.types,
        rarities=req.rarities,
        keywords=req.keywords,
        subtypes=req.subtypes,
        include_playtest=req.include_playtest,
        cmc_min=req.cmc_min,
        cmc_max=req.cmc_max,
        power_min=req.power_min,
        power_max=req.power_max,
        toughness_min=req.toughness_min,
        toughness_max=req.toughness_max,
        page=req.page,
        page_size=req.page_size,
    )


async def discover_exact_match(query: str, limit: int, **filters) -> dict:
    return await discover_cards(q=query, page=1, page_size=limit, **filters)


async def list_keywords() -> dict:
    return {"keywords": await get_all_keywords()}


async def list_card_prints(oracle_id: str) -> dict:
    return {"prints": await get_card_prints_by_oracle_id(oracle_id)}
