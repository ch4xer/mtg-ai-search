from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str


class SearchResponse(BaseModel):
    results: list[dict]


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
