from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=60, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    search_id: str | None = None


class SearchResponse(BaseModel):
    search_id: str | None = None
    results: list[dict]
    total: int | None = None
    limit: int | None = None
    offset: int = 0
    has_more: bool = False


class TagSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=12, ge=1, le=30)


class TagSearchMatch(BaseModel):
    tag: str
    tag_type: str
    label: str
    score: float
    reason: str
    search_query: str
    search_url: str


class TagSearchCatalogMeta(BaseModel):
    total_tags: int
    art_tags: int
    function_tags: int
    searched_tags: int | None = None
    etag: str | None = None
    loaded_at: str | None = None
    checked_at: str | None = None
    llm_used: bool = False
    query_rewrite_used: bool = False
    rewritten_intent: str = ""
    type_hint: str = "mixed"
    targets: list[dict] = Field(default_factory=list)
    logic: dict | None = None
    card_count: int = 0
    total_card_count: int = 0
    card_limit: int | None = None
    card_offset: int = 0
    card_filter_used: bool = False
    card_filters: dict = Field(default_factory=dict)
    card_filter_count: int | None = None
    card_filter_error: str = ""
    tag_retrieval_query: str = ""


class TagSearchResponse(BaseModel):
    query: str
    suggested_queries: list[str]
    matches: list[TagSearchMatch]
    cards: list[dict] = Field(default_factory=list)
    catalog: TagSearchCatalogMeta


class ApiAiSearchRequest(BaseModel):
    api_key: str
    query: str
    limit: int = Field(default=10, ge=1, le=50)
    rerank_enabled: bool = True
    rerank_top_n: int = Field(default=200, ge=1, le=200)


class ApiExactMatchRequest(BaseModel):
    api_key: str
    query: str = ""
    colors: list[str] | None = None
    types: list[str] | None = None
    rarities: list[str] | None = None
    keywords: list[str] | None = None
    subtypes: list[str] | None = None
    include_playtest: bool = False
    cmc_min: float | None = None
    cmc_max: float | None = None
    power_min: float | None = None
    power_max: float | None = None
    toughness_min: float | None = None
    toughness_max: float | None = None
    limit: int = Field(default=10, ge=1, le=100)


class DiscoverRequest(BaseModel):
    q: str = ""
    colors: list[str] | None = None
    types: list[str] | None = None
    rarities: list[str] | None = None
    keywords: list[str] | None = None
    subtypes: list[str] | None = None
    include_playtest: bool = False
    cmc_min: float | None = None
    cmc_max: float | None = None
    power_min: float | None = None
    power_max: float | None = None
    toughness_min: float | None = None
    toughness_max: float | None = None
    page: int = 1
    page_size: int = 60
