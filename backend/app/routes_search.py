"""Search and discovery HTTP endpoints."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from .dependencies import get_optional_user
from .schemas.search import (
    CardFunctionTagsResponse,
    DiscoverRequest,
    RandomCardResponse,
    SearchRequest,
    SearchResponse,
)
from .services.search_service import (
    card_function_tags as card_function_tags_service,
    discover as discover_service,
    get_client_ip,
    list_card_sets as list_card_sets_service,
    list_card_prints as list_card_prints_service,
    list_keyword_abilities as list_keyword_abilities_service,
    random_card as random_card_service,
    list_keywords as list_keywords_service,
    search_cards_result as search_cards_service,
)
search_router = APIRouter(tags=["search"])
logger = logging.getLogger(__name__)


@search_router.post("/api/search", response_model=SearchResponse)
async def search_cards(
    request: SearchRequest,
    raw_request: Request,
    user_id: str | None = Depends(get_optional_user),
):
    started = time.perf_counter()
    client_ip = get_client_ip(raw_request)
    logger.debug(
        ">>> /api/search query=%r limit=%d offset=%d search_id=%s user=%s ip=%s",
        request.query,
        request.limit,
        request.offset,
        request.search_id or "-",
        user_id or "anonymous",
        client_ip,
    )
    results = await search_cards_service(
        request.query,
        client_ip,
        user_id,
        card_limit=request.limit,
        card_offset=request.offset,
        search_id=request.search_id,
    )
    logger.debug(
        "<<< /api/search returned %d cards in %.2fs",
        len(results["results"]),
        time.perf_counter() - started,
    )
    return SearchResponse(**results)


@search_router.post("/api/discover")
async def discover(request: DiscoverRequest):
    return await discover_service(request)


@search_router.get("/api/keywords")
async def list_keywords():
    """Return all keyword abilities from the database."""
    return await list_keywords_service()


@search_router.get("/api/card-sets")
async def list_card_sets():
    """Return searchable print-set metadata from the local card catalog."""
    return await list_card_sets_service()


@search_router.get("/api/keyword-abilities")
async def list_keyword_abilities():
    """Return short bilingual explanations for card keyword abilities."""
    return await list_keyword_abilities_service()


@search_router.get("/api/cards/random", response_model=RandomCardResponse)
async def get_random_card(exclude_card_id: str | None = None):
    card = await random_card_service(exclude_card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="没有可供随机选择的卡牌")
    return {"card": card}


@search_router.get("/api/cards/{oracle_id}/function-tags", response_model=CardFunctionTagsResponse)
async def get_card_function_tags(oracle_id: str):
    result = await card_function_tags_service(oracle_id)
    if result is None:
        raise HTTPException(status_code=404, detail="卡牌不存在")
    return result


@search_router.get("/api/cards/{oracle_id}/prints")
async def get_card_prints(oracle_id: str):
    """Return all print versions for a card from the local database."""
    return await list_card_prints_service(oracle_id)
