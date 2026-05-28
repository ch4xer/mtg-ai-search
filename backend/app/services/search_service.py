"""Card search and discover workflows."""

import asyncio

from fastapi import HTTPException, Request

from ..config import get_rate_limits
from ..repositories.ai_search_sessions import create_ai_search_session, get_ai_search_session
from ..repositories.cards import discover_cards, get_all_keywords, get_card_prints_by_oracle_id
from ..repositories.search_logs import get_ip_hourly_search_count, get_user_hourly_search_count, log_search
from ..repositories.users import get_user_by_id
from ..schemas.search import DiscoverRequest
from .tag_search_service import search_tags, search_tags_from_plan


AI_SEARCH_SESSION_TTL_SECONDS = 60 * 60


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
    card_limit: int = 60,
    card_offset: int = 0,
    include_zh: bool = False,
) -> list[dict]:
    result = await search_cards_result(
        query,
        client_ip,
        user_id,
        rerank_enabled=rerank_enabled,
        rerank_top_n=rerank_top_n,
        card_limit=card_limit,
        card_offset=card_offset,
        include_zh=include_zh,
        create_session=False,
    )
    return result["results"]


async def search_cards_result(
    query: str,
    client_ip: str,
    user_id: str | None,
    *,
    rerank_enabled: bool = True,
    rerank_top_n: int = 200,
    card_limit: int = 60,
    card_offset: int = 0,
    search_id: str | None = None,
    create_session: bool = True,
    include_zh: bool = False,
) -> dict:
    offset = max(0, card_offset)
    limit = max(0, card_limit)

    if search_id:
        session = await get_ai_search_session(search_id=search_id, user_id=user_id, ip_address=client_ip)
        if session is None:
            raise HTTPException(status_code=404, detail="搜索会话已过期，请重新搜索")
        search_result = await search_tags_from_plan(
            session["query"],
            session["plan"],
            card_limit=limit,
            card_offset=offset,
        )
        total = int(search_result.get("catalog", {}).get("total_card_count") or len(search_result["cards"]))
        return {
            "search_id": search_id,
            "results": search_result["cards"],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(search_result["cards"]) < total,
        }

    if offset > 0:
        raise HTTPException(status_code=400, detail="加载更多需要 search_id，请重新搜索")

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

    search_result = await search_tags(query, card_limit=limit, card_offset=offset)
    new_search_id = None
    if create_session and search_result.get("search_plan"):
        new_search_id = await create_ai_search_session(
            query=query.strip(),
            plan=search_result["search_plan"],
            user_id=user_id,
            ip_address=client_ip,
            ttl_seconds=AI_SEARCH_SESSION_TTL_SECONDS,
        )
    asyncio.create_task(
        log_search(
            user_id,
            query,
            int(search_result.get("catalog", {}).get("card_filter_tokens_prompt") or 0),
            int(search_result.get("catalog", {}).get("card_filter_tokens_completion") or 0),
            ip_address=client_ip,
        )
    )
    total = int(search_result.get("catalog", {}).get("total_card_count") or len(search_result["cards"]))
    return {
        "search_id": new_search_id,
        "results": search_result["cards"],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(search_result["cards"]) < total,
    }


async def discover(req: DiscoverRequest) -> dict:
    result = await discover_cards(
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
    return result


async def discover_exact_match(query: str, limit: int, **filters) -> dict:
    return await discover_cards(q=query, page=1, page_size=limit, **filters)


async def list_keywords() -> dict:
    return {"keywords": await get_all_keywords()}


async def list_card_prints(oracle_id: str) -> dict:
    return {"prints": await get_card_prints_by_oracle_id(oracle_id)}
