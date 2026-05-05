"""Standalone Scryfall Tagger search service."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from html import unescape
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import httpx
from langchain_core.messages import HumanMessage, SystemMessage

from ..embedding import encode_batch_safe, encode_query
from ..llm_provider import create_chat_llm, is_chat_provider_configured
from ..repositories.cards import filter_cards, get_cards_by_ids
from ..repositories.database import get_pool
from .card_query_constraints import build_structured_card_filters, extract_card_search_constraints

logger = logging.getLogger(__name__)

TAGGER_TAGS_URL = "https://scryfall.com/docs/tagger-tags"
SCRYFALL_SEARCH_URL = "https://scryfall.com/search?q="
SCRYFALL_API_CARDS_SEARCH_URL = "https://api.scryfall.com/cards/search"
REFRESH_INTERVAL = timedelta(hours=12)
USER_AGENT = "MTG-AI-Search/1.0 (+https://github.com/ch4ser/MTG-AI-Search)"
SAMPLE_CARDS_PER_TAG = 3
SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS = float(os.getenv("SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS", "0.35"))
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TAG_EXPANSION_CACHE_PATH = DATA_DIR / "tag_expansions.json"
TAG_EXPANSION_CACHE_VERSION = 1
TAG_EXPANSION_DB_VERSION = 1
TAG_VECTOR_SEARCH_LIMIT = 40
RRF_K = 60

ART_HINTS = (
    "art",
    "artist",
    "illustration",
    "picture",
    "scene",
    "visual",
    "画",
    "插画",
    "图",
    "画面",
    "背景",
    "构图",
    "人物",
)
FUNCTION_HINTS = (
    "function",
    "effect",
    "oracle",
    "ability",
    "gameplay",
    "mechanic",
    "规则",
    "功能",
    "效果",
    "异能",
    "机制",
    "能力",
    "检索",
    "加速",
    "清场",
    "去除",
    "抓牌",
    "弃牌",
)
SUPPORTED_TAG_TYPES: set[Literal["function"]] = {"function"}

PHRASE_EXPANSIONS: dict[str, list[str]] = {
    "清场": ["wipe", "wrath of god", "mass removal"],
    "全场去除": ["wipe", "wrath of god", "mass removal"],
    "去除": ["removal", "destroy", "exile"],
    "解牌": ["removal", "destroy", "exile"],
    "抓牌": ["draw", "draw cards", "card advantage"],
    "过牌": ["draw", "draw cards"],
    "弃牌": ["discard"],
    "加速": ["ramp", "acceleration", "adds mana"],
    "反击": ["counterspell", "counter"],
    "墓地": ["graveyard", "cemetery", "tomb"],
    "坟场": ["graveyard", "cemetery", "tomb"],
    "牺牲": ["sacrifice"],
    "回血": ["lifegain", "gain life", "life gain"],
    "吸血": ["lifelink"],
    "飞行": ["flying"],
    "先攻": ["first strike"],
    "警戒": ["vigilance"],
    "践踏": ["trample"],
    "龙": ["dragon"],
    "天使": ["angel"],
    "恶魔": ["demon"],
    "乌鸦": ["raven", "crow"],
    "骷髅": ["skeleton", "skull"],
    "僵尸": ["zombie"],
    "吸血鬼": ["vampire"],
    "猫": ["cat"],
    "狼": ["wolf"],
    "火焰": ["fire", "flame"],
    "森林": ["forest", "tree", "woods"],
    "阴森": ["dark", "gloom", "spooky"],
}

TAG_SELECTION_PROMPT = (
    "You map Magic: The Gathering natural-language requests to Scryfall Tagger tags.\n"
    "Pick only from the provided candidates. Never invent a tag.\n"
    "Prefer the smallest set of tags that directly satisfies the request.\n"
    "Preserve all gameplay qualifiers from the request when selecting tags; repeatable/recurring effects are not equivalent to one-shot effects.\n"
    "Do not choose a generic one-shot tag over a repeatable/recurring tag when the request explicitly asks for repeatability.\n"
    "Candidates may include a target slot. Preserve useful tags for each required slot so the final Boolean query remains faithful.\n"
    "Treat art tags as visual/illustration concepts and function tags as Oracle/gameplay concepts.\n"
    "Return JSON only in this shape: "
    '{"selected":[{"id":1,"reason":"short reason"}]}.'
)

QUERY_REWRITE_PROMPT = (
    "You rewrite multilingual Magic: The Gathering tag-search requests into English retrieval intent.\n"
    "The search index contains only Scryfall functional/Oracle tags, not artwork tags.\n"
    "Rewrite the query toward MTG rules text, Oracle text, mechanics, gameplay effects, deck roles, and card behavior.\n"
    "Strict meaning preservation rules:\n"
    "- Do not weaken, broaden, simplify, or summarize away gameplay qualifiers from the user request.\n"
    "- Preserve actor, target, quantity, plurality, frequency, repeatability, duration, trigger condition, zone, timing, and restrictions.\n"
    "- A repeated/recurring/repeatable/each-turn/whenever effect is materially different from a one-shot effect. Never rewrite it as a one-shot effect.\n"
    "- If the user has a typo such as repeatly, infer repeatedly but keep the repeated/repeatable meaning.\n"
    "- If unsure whether a qualifier matters, keep it in intent and expanded_queries.\n"
    "Return JSON only with exactly these keys: "
    "intent_type, intent, core_concepts, expanded_queries, excluded_concepts, targets, logic.\n"
    "intent_type must always be function.\n"
    "intent must be one concise English sentence.\n"
    "core_concepts, expanded_queries, and excluded_concepts must be English string arrays.\n"
    "targets must be an array of focused functional retrieval goals. Each target must have: slot, type, intent, expanded_queries.\n"
    "Each target type must be function.\n"
    "Create multiple targets when the user asks for multiple gameplay concepts.\n"
    "logic must be a Boolean tree that preserves the user's requested relationship between targets.\n"
    "logic operator nodes use {'op':'and'|'or','children':[...]}.\n"
    "logic leaf nodes are self-contained targets using {'slot':'short_snake_case','type':'function','intent':'...','expanded_queries':[...]}.\n"
    "Use and when all concepts must be true. Use or when any alternative effect may satisfy the user.\n"
    "Never combine alternatives connected by or/或者/任一 into one leaf. Use an or node with one child per alternative.\n"
    "Example: 'from graveyard and discard or lose life' must become and(graveyard, or(discard, life_loss)).\n"
    "expanded_queries should contain 4 to 10 short English retrieval phrases suitable for semantic search over tag descriptions.\n"
    "Keep expansions faithful to the user's wording. If the user only asks for visual/art concepts, describe the closest functional intent as empty or broad, but do not create artwork targets.\n"
    "Example: 'repeatly create token and discards opponent card' must preserve repeatability as repeated/repeatable token creation, not just create a token.\n"
)

TAG_EXPANSION_PROMPT = (
    "You generate English retrieval metadata for Scryfall Tagger tags.\n"
    "The metadata is used only for semantic retrieval. Keep it faithful to the tag name.\n"
    "The tag type is context only; do not include the words art, artwork, function, gameplay, or Oracle merely because of the type.\n"
    "Each tag may include sample cards returned by Scryfall for that tag. Use those cards to infer the functional meaning when the tag name is ambiguous.\n"
    "The sample cards are evidence, not exhaustive definitions. Generalize from their shared gameplay pattern.\n"
    "Do not invent card names or claim official definitions. Do not add explicit sexual content unless the tag itself clearly implies it.\n"
    "For art tags, describe visual subjects, objects, compositions, moods, locations, character traits, clothing, or art tropes.\n"
    "For function tags, describe MTG gameplay effects, mechanics, deck roles, and Oracle-text concepts.\n"
    "Return JSON only in this shape: "
    '{"items":[{"key":"art:example-tag","aliases":["..."],"retrieval_phrases":["..."],"description":"..."}]}.\n'
    "aliases must have 1 to 5 short English aliases.\n"
    "retrieval_phrases must have 3 to 8 short English search phrases.\n"
    "description must be one concise English sentence.\n"
)


@dataclass(frozen=True)
class QueryTarget:
    type_hint: Literal["function"]
    intent: str
    expansions: tuple[str, ...]
    slot: str = "target_1"


@dataclass(frozen=True)
class QueryLogicNode:
    op: Literal["and", "or", "target"]
    slot: str = ""
    target_index: int | None = None
    children: tuple["QueryLogicNode", ...] = ()


@dataclass(frozen=True)
class QueryAnalysis:
    type_hint: Literal["art", "function", "mixed"]
    intent: str
    expansions: tuple[str, ...]
    excluded_concepts: tuple[str, ...]
    rewrite_used: bool
    targets: tuple[QueryTarget, ...] = ()
    logic: QueryLogicNode | None = None


@dataclass(frozen=True)
class TagEntry:
    tag: str
    tag_type: Literal["art", "function"]
    normalized: str
    tokens: frozenset[str]
    label: str
    aliases: tuple[str, ...] = ()
    retrieval_phrases: tuple[str, ...] = ()
    description: str = ""
    embedding_text: str = ""
    semantic_tokens: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CatalogSnapshot:
    entries: tuple[TagEntry, ...]
    etag: str | None
    loaded_at: str | None
    checked_at: str | None
    content_hash: str


@dataclass(frozen=True)
class FetchedTagPage:
    entries: tuple[TagEntry, ...]
    etag: str | None
    checked_at: str
    content_hash: str
    not_modified: bool = False


class _TaggerTagHTMLParser:
    section_pattern = re.compile(r"<h2[^>]*>(.*?)</h2>\s*<p>(.*?)</p>", re.IGNORECASE | re.DOTALL)
    strip_pattern = re.compile(r"<[^>]+>")

    @classmethod
    def parse(cls, html: str) -> tuple[tuple[TagEntry, ...], str]:
        entries: list[TagEntry] = []
        chunks: list[str] = []
        for raw_heading, raw_body in cls.section_pattern.findall(html):
            heading = cls._clean(raw_heading)
            body = cls._clean(raw_body)
            if not heading or not body:
                continue
            if len(heading) > 24 and "functional" not in heading.lower():
                continue

            tag_type: Literal["art", "function"] = "function" if "functional" in heading.lower() else "art"
            raw_tags = [item.strip() for item in body.split("·")]
            filtered_tags = [tag for tag in raw_tags if tag and " " not in tag]
            if not filtered_tags:
                continue

            for tag in filtered_tags:
                normalized = _normalize(tag)
                entries.append(
                    TagEntry(
                        tag=tag,
                        tag_type=tag_type,
                        normalized=normalized,
                        tokens=frozenset(_tokenize(normalized)),
                        label=tag.replace("-", " "),
                    )
                )
            chunks.append(f"{heading}:{'|'.join(filtered_tags)}")

        deduped = tuple(
            entry
            for entry in {(entry.tag_type, entry.tag): entry for entry in entries}.values()
            if entry.tag_type in SUPPORTED_TAG_TYPES
        )
        digest_source = "\n".join(f"{entry.tag_type}:{entry.tag}" for entry in deduped)
        digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
        return deduped, digest

    @classmethod
    def _clean(cls, text: str) -> str:
        return " ".join(unescape(cls.strip_pattern.sub(" ", text)).split())


async def _fetch_tagger_tags_page(etag: str | None = None) -> FetchedTagPage:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if etag:
        headers["If-None-Match"] = etag

    checked_at = datetime.now(timezone.utc).isoformat()
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(TAGGER_TAGS_URL, headers=headers)

    if response.status_code == 304:
        return FetchedTagPage(
            entries=(),
            etag=etag,
            checked_at=checked_at,
            content_hash="",
            not_modified=True,
        )

    response.raise_for_status()
    entries, content_hash = _TaggerTagHTMLParser.parse(response.text)
    return FetchedTagPage(
        entries=entries,
        etag=response.headers.get("etag"),
        checked_at=checked_at,
        content_hash=content_hash,
    )


class TagCatalogStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._snapshot: CatalogSnapshot | None = None
        self._last_refresh_at: datetime | None = None

    async def get_snapshot(self) -> CatalogSnapshot:
        if self._snapshot is None or self._is_stale():
            await self._refresh()
        if self._snapshot is None:
            raise RuntimeError("Tag catalog is unavailable")
        return self._snapshot

    def _is_stale(self) -> bool:
        if self._last_refresh_at is None:
            return True
        return datetime.now(timezone.utc) - self._last_refresh_at >= REFRESH_INTERVAL

    async def _refresh(self) -> None:
        async with self._lock:
            if self._snapshot is not None and not self._is_stale():
                return

            try:
                db_snapshot = await _load_entries_from_db()
            except Exception:
                logger.exception("Failed to load tagger tags from database; falling back to Scryfall")
                db_snapshot = None

            if db_snapshot is not None:
                self._snapshot = db_snapshot
                self._last_refresh_at = datetime.now(timezone.utc)
                return

            fetched = await _fetch_tagger_tags_page(self._snapshot.etag if self._snapshot else None)
            if fetched.not_modified and self._snapshot is not None:
                entries = self._snapshot.entries
                content_hash = self._snapshot.content_hash
                loaded_at = self._snapshot.loaded_at
            else:
                entries = fetched.entries
                content_hash = fetched.content_hash
                loaded_at = datetime.now(timezone.utc).isoformat()

            self._snapshot = CatalogSnapshot(
                entries=entries,
                etag=fetched.etag,
                loaded_at=loaded_at,
                checked_at=fetched.checked_at,
                content_hash=content_hash,
            )
            self._last_refresh_at = datetime.now(timezone.utc)


catalog_store = TagCatalogStore()


def _tag_key(tag_type: str, tag: str) -> str:
    return f"{tag_type}:{tag}"


def _fallback_embedding_text(tag: str, tag_type: str, label: str) -> str:
    return f"tag: {label}."


def _entry_content_hash(entry: TagEntry) -> str:
    payload = {
        "tag": entry.tag,
        "tag_type": entry.tag_type,
        "label": entry.label,
        "normalized": entry.normalized,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _read_tag_expansion_payload() -> dict:
    try:
        with TAG_EXPANSION_CACHE_PATH.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        return {"version": TAG_EXPANSION_CACHE_VERSION, "items": {}}
    except Exception:
        logger.exception("Failed to load tag expansion cache")
        return {"version": TAG_EXPANSION_CACHE_VERSION, "items": {}}

    if not isinstance(payload, dict):
        return {"version": TAG_EXPANSION_CACHE_VERSION, "items": {}}
    if not isinstance(payload.get("items"), dict):
        payload["items"] = {}
    return payload


def _write_tag_expansion_payload(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = TAG_EXPANSION_CACHE_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    tmp_path.replace(TAG_EXPANSION_CACHE_PATH)


async def _persist_generated_expansions(generated: dict[str, dict]) -> None:
    if not generated:
        return

    pool = await get_pool()
    now = datetime.now(timezone.utc)
    rows = []
    for item in generated.values():
        generated_at = item.get("updated_at")
        try:
            expansion_generated_at = datetime.fromisoformat(generated_at) if generated_at else now
        except ValueError:
            expansion_generated_at = now
        rows.append(
            (
                json.dumps(item.get("aliases", [])),
                json.dumps(item.get("retrieval_phrases", [])),
                item.get("description", ""),
                item.get("embedding_text", ""),
                expansion_generated_at,
                item.get("source", "deepseek"),
                item.get("model", ""),
                TAG_EXPANSION_DB_VERSION,
                now,
                item.get("tag_type", "function"),
                item.get("tag", ""),
            )
        )

    async with pool.acquire() as conn:
        await conn.execute("ALTER TABLE tagger_tags ADD COLUMN IF NOT EXISTS embedding halfvec(2560)")
        await conn.execute("ALTER TABLE tagger_tags ADD COLUMN IF NOT EXISTS expansion_generated_at TIMESTAMPTZ")
        await conn.execute("ALTER TABLE tagger_tags ADD COLUMN IF NOT EXISTS expansion_source TEXT")
        await conn.execute("ALTER TABLE tagger_tags ADD COLUMN IF NOT EXISTS expansion_model TEXT")
        await conn.execute(
            "ALTER TABLE tagger_tags ADD COLUMN IF NOT EXISTS expansion_version INT NOT NULL DEFAULT 1"
        )
        await conn.executemany(
            """
            UPDATE tagger_tags
            SET aliases = $1::jsonb,
                retrieval_phrases = $2::jsonb,
                description = $3,
                embedding_text = $4,
                expansion_generated_at = $5,
                expansion_source = $6,
                expansion_model = $7,
                expansion_version = $8,
                embedding = CASE
                    WHEN embedding_text IS DISTINCT FROM $4 THEN NULL
                    ELSE embedding
                END,
                updated_at = $9
            WHERE tag_type = $10 AND tag = $11
            """,
            rows,
        )


async def _load_generated_expansion_items_from_db() -> dict[str, dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT tag, tag_type, label, aliases, retrieval_phrases, description, embedding_text, updated_at
        FROM tagger_tags
        WHERE removed_at IS NULL
          AND tag_type = 'function'
          AND embedding_text <> ''
        ORDER BY tag
        """
    )

    items: dict[str, dict] = {}
    for row in rows:
        fallback_text = _fallback_embedding_text(row["tag"], row["tag_type"], row["label"])
        if row["embedding_text"] == fallback_text:
            continue
        key = _tag_key(row["tag_type"], row["tag"])
        items[key] = {
            "tag": row["tag"],
            "tag_type": row["tag_type"],
            "label": row["label"],
            "aliases": _as_string_list(row["aliases"], max_items=5),
            "retrieval_phrases": _as_string_list(row["retrieval_phrases"], max_items=8),
            "description": row["description"] or "",
            "embedding_text": row["embedding_text"],
            "sample_cards": [],
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else datetime.now(timezone.utc).isoformat(),
            "source": "database",
        }
    return items


async def _load_expansion_work_from_db(
    *,
    limit: int | None,
    force: bool,
    tag_types: set[str] | None,
) -> tuple[list[TagEntry], int]:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT
            tag,
            tag_type,
            label,
            normalized,
            aliases,
            retrieval_phrases,
            description,
            embedding_text,
            expansion_generated_at
        FROM tagger_tags
        WHERE removed_at IS NULL
          AND tag_type = 'function'
        ORDER BY tag
        """
    )

    pending: list[TagEntry] = []
    existing_count = 0
    for row in rows:
        tag_type = row["tag_type"]
        if tag_types and tag_type not in tag_types:
            continue

        tag = row["tag"]
        label = row["label"]
        normalized = row["normalized"]
        aliases = tuple(_as_string_list(row["aliases"], max_items=12))
        retrieval_phrases = tuple(_as_string_list(row["retrieval_phrases"], max_items=16))
        description = row["description"] or ""
        embedding_text = row["embedding_text"] or ""
        fallback_text = _fallback_embedding_text(tag, tag_type, label)
        has_expansion = row["expansion_generated_at"] is not None or (
            bool(embedding_text) and embedding_text != fallback_text
        )

        if has_expansion and not force:
            existing_count += 1
            continue
        if limit is not None and limit <= 0:
            continue

        semantic_text = " ".join(
            item
            for item in (
                normalized,
                embedding_text,
                " ".join(aliases),
                " ".join(retrieval_phrases),
                description,
            )
            if item
        )
        pending.append(
            TagEntry(
                tag=tag,
                tag_type=tag_type,
                normalized=normalized,
                tokens=frozenset(_tokenize(normalized)),
                label=label,
                aliases=aliases,
                retrieval_phrases=retrieval_phrases,
                description=description,
                embedding_text=embedding_text or fallback_text,
                semantic_tokens=frozenset(_tokenize(_normalize(semantic_text))),
            )
        )
        if limit is not None and len(pending) >= limit:
            break

    return pending, existing_count


def _build_embedding_text(
    tag: str,
    tag_type: str,
    label: str,
    aliases: list[str],
    retrieval_phrases: list[str],
    description: str,
) -> str:
    parts = [
        f"tag: {label}",
    ]
    if aliases:
        parts.append(f"aliases: {'; '.join(aliases)}")
    if retrieval_phrases:
        parts.append(f"retrieval phrases: {'; '.join(retrieval_phrases)}")
    if description:
        parts.append(f"description: {description}")
    return ". ".join(parts) + "."


def _card_oracle_text(card: dict) -> str:
    oracle_text = card.get("oracle_text")
    if isinstance(oracle_text, str) and oracle_text.strip():
        return " ".join(oracle_text.split())

    faces = card.get("card_faces")
    if isinstance(faces, list):
        chunks = []
        for face in faces:
            if not isinstance(face, dict):
                continue
            text = face.get("oracle_text")
            if isinstance(text, str) and text.strip():
                chunks.append(" ".join(text.split()))
        return " // ".join(chunks)
    return ""


def _sample_card_from_scryfall(card: dict) -> dict:
    oracle_text = _card_oracle_text(card)
    if len(oracle_text) > 420:
        oracle_text = oracle_text[:417].rstrip() + "..."
    return {
        "name": card.get("name", ""),
        "type_line": card.get("type_line", ""),
        "oracle_text": oracle_text,
    }


def _fetch_sample_cards_for_tag(entry: TagEntry, sample_size: int = SAMPLE_CARDS_PER_TAG) -> list[dict]:
    if sample_size <= 0:
        return []

    query = f'{entry.tag_type}:"{entry.tag}"'
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                response = client.get(
                    SCRYFALL_API_CARDS_SEARCH_URL,
                    params={
                        "q": query,
                        "unique": "cards",
                        "order": "name",
                    },
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json",
                    },
                )
            if response.status_code == 404:
                return []
            response.raise_for_status()
            payload = response.json()
            break
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 1.5)
    else:
        logger.warning(
            "Failed to fetch sample cards for tag %s after retries: %s",
            _tag_key(entry.tag_type, entry.tag),
            last_error,
        )
        return []

    cards = payload.get("data", [])
    if not isinstance(cards, list):
        return []
    return [_sample_card_from_scryfall(card) for card in cards[:sample_size] if isinstance(card, dict)]


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vector) + "]"


async def _get_tag_sync_state() -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT source_url, etag, content_hash, checked_at, updated_at, total_tags, art_tags, function_tags
        FROM tag_sync_state
        WHERE source_url = $1
        """,
        TAGGER_TAGS_URL,
    )
    return dict(row) if row else None


async def _load_entries_from_db() -> CatalogSnapshot | None:
    pool = await get_pool()
    state = await _get_tag_sync_state()
    rows = await pool.fetch(
        """
        SELECT tag, tag_type, label, normalized, aliases, retrieval_phrases, description, embedding_text
        FROM tagger_tags
        WHERE removed_at IS NULL
          AND tag_type = 'function'
        ORDER BY tag_type, tag
        """
    )
    if not rows:
        return None

    entries: list[TagEntry] = []
    for row in rows:
        tag = row["tag"]
        tag_type = row["tag_type"]
        normalized = row["normalized"]
        aliases = tuple(_as_string_list(row["aliases"], max_items=12))
        retrieval_phrases = tuple(_as_string_list(row["retrieval_phrases"], max_items=16))
        description = row["description"] or ""
        embedding_text = row["embedding_text"] or _fallback_embedding_text(tag, tag_type, row["label"])
        semantic_text = " ".join(
            item
            for item in (
                normalized,
                embedding_text,
                " ".join(aliases),
                " ".join(retrieval_phrases),
                description,
            )
            if item
        )
        entries.append(
            TagEntry(
                tag=tag,
                tag_type=tag_type,
                normalized=normalized,
                tokens=frozenset(_tokenize(normalized)),
                label=row["label"],
                aliases=aliases,
                retrieval_phrases=retrieval_phrases,
                description=description,
                embedding_text=embedding_text,
                semantic_tokens=frozenset(_tokenize(_normalize(semantic_text))),
            )
        )

    return CatalogSnapshot(
        entries=tuple(entries),
        etag=state.get("etag") if state else None,
        loaded_at=state["updated_at"].isoformat() if state and state.get("updated_at") else None,
        checked_at=state["checked_at"].isoformat() if state and state.get("checked_at") else None,
        content_hash=state.get("content_hash") if state else "",
    )


async def _persist_tag_entries(
    entries: tuple[TagEntry, ...],
    *,
    etag: str | None,
    checked_at: str,
    content_hash: str,
) -> dict:
    pool = await get_pool()
    now = datetime.now(timezone.utc)
    art_tags = sum(1 for entry in entries if entry.tag_type == "art")
    function_tags = len(entries) - art_tags

    async with pool.acquire() as conn:
        async with conn.transaction():
            active_rows = await conn.fetch(
                """
                SELECT tag_type, tag
                FROM tagger_tags
                WHERE removed_at IS NULL
                """
            )
            active_keys = {(row["tag_type"], row["tag"]) for row in active_rows}
            incoming_keys = {(entry.tag_type, entry.tag) for entry in entries}
            removed_keys = active_keys - incoming_keys

            await conn.execute(
                """
                UPDATE tagger_tags
                SET removed_at = $1, updated_at = $1
                WHERE removed_at IS NULL
                """,
                now,
            )

            await conn.executemany(
                """
                INSERT INTO tagger_tags (
                    tag, tag_type, label, normalized, aliases, retrieval_phrases, description,
                    embedding_text, expansion_version, content_hash, first_seen_at, updated_at, removed_at
                )
                VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9, $10, $11, $11, NULL)
                ON CONFLICT (tag_type, tag) DO UPDATE SET
                    label = EXCLUDED.label,
                    normalized = EXCLUDED.normalized,
                    content_hash = EXCLUDED.content_hash,
                    updated_at = EXCLUDED.updated_at,
                    removed_at = NULL
                """,
                [
                    (
                        entry.tag,
                        entry.tag_type,
                        entry.label,
                        entry.normalized,
                        json.dumps(list(entry.aliases)),
                        json.dumps(list(entry.retrieval_phrases)),
                        entry.description,
                        entry.embedding_text or _fallback_embedding_text(entry.tag, entry.tag_type, entry.label),
                        TAG_EXPANSION_DB_VERSION,
                        _entry_content_hash(entry),
                        now,
                    )
                    for entry in entries
                ],
            )

            await conn.execute(
                """
                INSERT INTO tag_sync_state (
                    source_url, etag, content_hash, checked_at, updated_at,
                    total_tags, art_tags, function_tags
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (source_url) DO UPDATE SET
                    etag = EXCLUDED.etag,
                    content_hash = EXCLUDED.content_hash,
                    checked_at = EXCLUDED.checked_at,
                    updated_at = EXCLUDED.updated_at,
                    total_tags = EXCLUDED.total_tags,
                    art_tags = EXCLUDED.art_tags,
                    function_tags = EXCLUDED.function_tags
                """,
                TAGGER_TAGS_URL,
                etag,
                content_hash,
                datetime.fromisoformat(checked_at),
                now,
                len(entries),
                art_tags,
                function_tags,
            )

    return {
        "total_tags": len(entries),
        "art_tags": art_tags,
        "function_tags": function_tags,
        "removed_tags": len(removed_keys),
        "removed_function_tags": sum(1 for tag_type, _ in removed_keys if tag_type == "function"),
    }


async def update_tagger_tags_if_changed(*, force: bool = False) -> dict:
    """Check Scryfall's Tagger tag page and refresh the local DB cache if needed.

    ETag is used as the cheap network signature. The parsed tag-list hash is
    stored as the data signature, so HTML-only changes do not force downstream
    work.
    """
    state = await _get_tag_sync_state()
    previous_etag = state.get("etag") if state and not force else None
    fetched = await _fetch_tagger_tags_page(previous_etag)
    checked_at_dt = datetime.fromisoformat(fetched.checked_at)

    pool = await get_pool()
    if fetched.not_modified and state:
        await pool.execute(
            """
            UPDATE tag_sync_state
            SET checked_at = $1
            WHERE source_url = $2
            """,
            checked_at_dt,
            TAGGER_TAGS_URL,
        )
        return {
            "status": "skipped",
            "reason": "etag_not_modified",
            "etag": previous_etag,
            "content_hash": state.get("content_hash"),
            "checked_at": fetched.checked_at,
            "total_tags": state.get("total_tags", 0),
        }

    if state and not force and fetched.content_hash == state.get("content_hash"):
        await pool.execute(
            """
            INSERT INTO tag_sync_state (
                source_url, etag, content_hash, checked_at, updated_at,
                total_tags, art_tags, function_tags
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (source_url) DO UPDATE SET
                etag = EXCLUDED.etag,
                checked_at = EXCLUDED.checked_at
            """,
            TAGGER_TAGS_URL,
            fetched.etag,
            fetched.content_hash,
            checked_at_dt,
            state.get("updated_at") or checked_at_dt,
            state.get("total_tags", 0),
            state.get("art_tags", 0),
            state.get("function_tags", 0),
        )
        return {
            "status": "skipped",
            "reason": "content_hash_unchanged",
            "etag": fetched.etag,
            "content_hash": fetched.content_hash,
            "checked_at": fetched.checked_at,
            "total_tags": state.get("total_tags", 0),
        }

    if not fetched.entries:
        raise RuntimeError("Fetched Tagger tag list is empty; refusing to mark existing tags as removed")

    counts = await _persist_tag_entries(
        fetched.entries,
        etag=fetched.etag,
        checked_at=fetched.checked_at,
        content_hash=fetched.content_hash,
    )
    catalog_store._snapshot = None
    return {
        "status": "updated",
        "reason": "content_hash_changed" if state else "initial_sync",
        "etag": fetched.etag,
        "content_hash": fetched.content_hash,
        "checked_at": fetched.checked_at,
        **counts,
    }


async def _ensure_card_tagger_tags_schema() -> None:
    pool = await get_pool()
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS card_tagger_tags (
            tag_type           TEXT NOT NULL CHECK (tag_type IN ('art', 'function')),
            tag                TEXT NOT NULL,
            card_id            TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
            source_scryfall_id TEXT,
            synced_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (tag_type, tag, card_id),
            FOREIGN KEY (tag_type, tag) REFERENCES tagger_tags(tag_type, tag) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_card_tagger_tags_card_id ON card_tagger_tags(card_id);
        CREATE INDEX IF NOT EXISTS idx_card_tagger_tags_tag ON card_tagger_tags(tag_type, tag);

        CREATE TABLE IF NOT EXISTS tag_card_sync_state (
            tag_type           TEXT NOT NULL CHECK (tag_type IN ('art', 'function')),
            tag                TEXT NOT NULL,
            status             TEXT NOT NULL DEFAULT 'idle',
            api_card_count     INT NOT NULL DEFAULT 0,
            linked_card_count  INT NOT NULL DEFAULT 0,
            missing_card_count INT NOT NULL DEFAULT 0,
            last_error         TEXT NOT NULL DEFAULT '',
            synced_at          TIMESTAMPTZ,
            updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (tag_type, tag),
            FOREIGN KEY (tag_type, tag) REFERENCES tagger_tags(tag_type, tag) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_tag_card_sync_state_status ON tag_card_sync_state(status);
        """
    )


def _retry_after_seconds(response: httpx.Response, fallback_seconds: float) -> float:
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return fallback_seconds
    try:
        return max(float(retry_after), fallback_seconds)
    except ValueError:
        return fallback_seconds


async def _set_tag_card_sync_state(
    tag: str,
    status: str,
    *,
    api_card_count: int = 0,
    linked_card_count: int = 0,
    missing_card_count: int = 0,
    last_error: str = "",
) -> None:
    pool = await get_pool()
    now = datetime.now(timezone.utc)
    await pool.execute(
        """
        INSERT INTO tag_card_sync_state (
            tag_type, tag, status, api_card_count, linked_card_count,
            missing_card_count, last_error, synced_at, updated_at
        )
        VALUES (
            'function', $1, $2, $3, $4, $5, $6,
            CASE WHEN $2 = 'done' THEN $7::timestamptz ELSE NULL::timestamptz END,
            $7
        )
        ON CONFLICT (tag_type, tag) DO UPDATE SET
            status = EXCLUDED.status,
            api_card_count = EXCLUDED.api_card_count,
            linked_card_count = EXCLUDED.linked_card_count,
            missing_card_count = EXCLUDED.missing_card_count,
            last_error = EXCLUDED.last_error,
            synced_at = CASE
                WHEN EXCLUDED.status = 'done' THEN EXCLUDED.synced_at
                ELSE tag_card_sync_state.synced_at
            END,
            updated_at = EXCLUDED.updated_at
        """,
        tag,
        status,
        api_card_count,
        linked_card_count,
        missing_card_count,
        last_error[:1000],
        now,
    )


async def _fetch_function_tag_cards_from_scryfall(
    client: httpx.AsyncClient,
    tag: str,
    *,
    request_delay_seconds: float,
) -> list[dict]:
    url: str | None = SCRYFALL_API_CARDS_SEARCH_URL
    params: dict[str, str] | None = {
        "q": _single_tag_search_expr("function", tag),
        "unique": "cards",
        "order": "name",
    }
    cards: list[dict] = []

    while url:
        last_error: Exception | None = None
        payload: dict | None = None
        for attempt in range(1, 4):
            try:
                response = await client.get(url, params=params)
                if response.status_code == 404:
                    return cards
                if response.status_code == 429 and attempt < 3:
                    await asyncio.sleep(_retry_after_seconds(response, attempt * 2.0))
                    continue
                response.raise_for_status()
                payload = response.json()
                break
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    await asyncio.sleep(attempt * 1.5)
        if payload is None:
            raise RuntimeError(f"Failed to fetch Scryfall cards for function:{tag}: {last_error}")

        page_cards = payload.get("data", [])
        if isinstance(page_cards, list):
            cards.extend(card for card in page_cards if isinstance(card, dict))

        url = payload.get("next_page") if payload.get("has_more") else None
        params = None
        if url:
            await asyncio.sleep(request_delay_seconds)

    return cards


async def _persist_function_tag_cards(tag: str, scryfall_cards: list[dict]) -> dict:
    oracle_source_ids: dict[str, str] = {}
    for card in scryfall_cards:
        oracle_id = str(card.get("oracle_id") or "").strip()
        scryfall_id = str(card.get("id") or "").strip()
        if oracle_id:
            oracle_source_ids.setdefault(oracle_id, scryfall_id)

    pool = await get_pool()
    now = datetime.now(timezone.utc)
    oracle_ids = list(oracle_source_ids.keys())

    async with pool.acquire() as conn:
        async with conn.transaction():
            if oracle_ids:
                rows = await conn.fetch("SELECT id FROM cards WHERE id = ANY($1::text[])", oracle_ids)
                local_ids = [row["id"] for row in rows]
            else:
                local_ids = []

            if local_ids:
                await conn.executemany(
                    """
                    INSERT INTO card_tagger_tags (
                        tag_type, tag, card_id, source_scryfall_id, synced_at
                    )
                    VALUES ('function', $1, $2, $3, $4)
                    ON CONFLICT (tag_type, tag, card_id) DO UPDATE SET
                        source_scryfall_id = EXCLUDED.source_scryfall_id,
                        synced_at = EXCLUDED.synced_at
                    """,
                    [
                        (tag, card_id, oracle_source_ids.get(card_id), now)
                        for card_id in local_ids
                    ],
                )
                await conn.execute(
                    """
                    DELETE FROM card_tagger_tags
                    WHERE tag_type = 'function'
                      AND tag = $1
                      AND NOT (card_id = ANY($2::text[]))
                    """,
                    tag,
                    local_ids,
                )
            else:
                await conn.execute(
                    "DELETE FROM card_tagger_tags WHERE tag_type = 'function' AND tag = $1",
                    tag,
                )

    return {
        "api_cards": len(oracle_source_ids),
        "linked_cards": len(local_ids),
        "missing_cards": max(0, len(oracle_source_ids) - len(local_ids)),
    }


async def sync_function_tag_card_links(
    *,
    status_callback=None,
    request_delay_seconds: float = 0.1,
    only_failed: bool = False,
    limit: int | None = None,
) -> dict:
    """Refresh function tags and sync their matching card links from Scryfall."""

    def emit(message: str) -> None:
        if status_callback:
            status_callback(message)

    emit("正在更新 Scryfall function tag 列表...")
    tag_result = await update_tagger_tags_if_changed(force=True)
    removed_function_tags = int(tag_result.get("removed_function_tags") or 0)
    if removed_function_tags:
        emit(f"发现 {removed_function_tags} 个已移除 function tag，保留历史卡牌关系...")
    await _ensure_card_tagger_tags_schema()

    pool = await get_pool()
    if only_failed:
        rows = await pool.fetch(
            """
            SELECT tt.tag
            FROM tagger_tags tt
            JOIN tag_card_sync_state state
              ON state.tag_type = tt.tag_type
             AND state.tag = tt.tag
            WHERE tt.removed_at IS NULL
              AND tt.tag_type = 'function'
              AND state.status = 'error'
            ORDER BY tt.tag
            """
        )
    else:
        rows = await pool.fetch(
            """
            SELECT tag
            FROM tagger_tags
            WHERE removed_at IS NULL
              AND tag_type = 'function'
            ORDER BY tag
            """
        )
    tags = [row["tag"] for row in rows]
    if limit is not None:
        tags = tags[:max(0, limit)]
    total_tags = len(tags)
    processed = 0
    failed = 0
    api_cards = 0
    linked_cards = 0
    missing_cards = 0

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
        for index, tag in enumerate(tags, start=1):
            emit(f"正在同步 function:{tag}（{index}/{total_tags}）...")
            try:
                await _set_tag_card_sync_state(tag, "running")
                cards = await _fetch_function_tag_cards_from_scryfall(
                    client,
                    tag,
                    request_delay_seconds=request_delay_seconds,
                )
                stats = await _persist_function_tag_cards(tag, cards)
                processed += 1
                api_cards += stats["api_cards"]
                linked_cards += stats["linked_cards"]
                missing_cards += stats["missing_cards"]
                await _set_tag_card_sync_state(
                    tag,
                    "done",
                    api_card_count=stats["api_cards"],
                    linked_card_count=stats["linked_cards"],
                    missing_card_count=stats["missing_cards"],
                )
            except Exception as exc:
                failed += 1
                error_message = f"{type(exc).__name__}: {exc}"
                logger.exception(error_message)
                await _set_tag_card_sync_state(tag, "error", last_error=error_message)
            if index < total_tags:
                await asyncio.sleep(request_delay_seconds)

    try:
        await pool.execute(
            """INSERT INTO app_meta (key, value) VALUES ('last_function_tag_card_sync_at', $1)
               ON CONFLICT (key) DO UPDATE SET value = $1""",
            datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        logger.warning("Failed to write last_function_tag_card_sync_at metadata", exc_info=True)

    return {
        "tag_sync": tag_result,
        "total_tags": total_tags,
        "processed_tags": processed,
        "failed_tags": failed,
        "removed_function_tags": removed_function_tags,
        "api_cards": api_cards,
        "linked_cards": linked_cards,
        "missing_cards": missing_cards,
    }


def _normalize(text: str) -> str:
    text = unescape(text).lower().replace("_", " ").replace("-", " ")
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff\s]+", " ", text)
    return " ".join(text.split())


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text.lower())


def _detect_type_hint(query: str) -> Literal["art", "function", "mixed"]:
    return "function"


def _expand_query(query: str) -> list[str]:
    normalized = _normalize(query)
    expansions = [normalized]
    for phrase, mapped in PHRASE_EXPANSIONS.items():
        if phrase in query or phrase in normalized:
            expansions.extend(mapped)
    return list(dict.fromkeys(item for item in expansions if item))


def _fallback_query_analysis(query: str) -> QueryAnalysis:
    expansions = tuple(_expand_query(query))
    target = QueryTarget(
        type_hint="function",
        intent=_normalize(query),
        expansions=expansions,
        slot="target_1",
    )
    return QueryAnalysis(
        type_hint="function",
        intent=_normalize(query),
        expansions=expansions,
        excluded_concepts=(),
        rewrite_used=False,
        targets=(target,),
        logic=QueryLogicNode(op="target", slot=target.slot, target_index=0),
    )


def _as_string_list(value, *, max_items: int = 12) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [value]
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value[:max_items]:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split())
        if text:
            cleaned.append(text)
    return cleaned


def _sanitize_slot(value: object, fallback: str) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw or fallback


def _target_from_payload(item: dict, *, fallback_slot: str) -> QueryTarget | None:
    raw_target_type = str(item.get("type", "")).strip().lower()
    if raw_target_type != "function":
        return None

    target_intent = " ".join(str(item.get("intent", "")).split())
    target_expanded = _as_string_list(item.get("expanded_queries"), max_items=10)
    target_expansions = [target_intent, *target_expanded]
    if not any(target_expansions):
        return None

    return QueryTarget(
        type_hint="function",
        intent=target_intent,
        expansions=tuple(dict.fromkeys(item for item in target_expansions if item)),
        slot=_sanitize_slot(item.get("slot"), fallback_slot),
    )


def _parse_logic_node(
    value: object,
    targets: list[QueryTarget],
    *,
    path: str = "target",
) -> QueryLogicNode | None:
    if not isinstance(value, dict):
        return None

    op = str(value.get("op", "")).strip().lower()
    if op in {"and", "or"}:
        children = []
        raw_children = value.get("children", [])
        if isinstance(raw_children, list):
            for index, child in enumerate(raw_children[:8], start=1):
                parsed = _parse_logic_node(child, targets, path=f"{path}_{index}")
                if parsed is not None:
                    children.append(parsed)
        if not children:
            return None
        if len(children) == 1:
            return children[0]
        return QueryLogicNode(op=op, children=tuple(children))

    target = _target_from_payload(value, fallback_slot=f"{path}_{len(targets) + 1}")
    if target is None:
        return None
    target_index = len(targets)
    targets.append(target)
    return QueryLogicNode(op="target", slot=target.slot, target_index=target_index)


def _logic_from_targets(targets: tuple[QueryTarget, ...]) -> QueryLogicNode | None:
    if not targets:
        return None
    leaves = tuple(
        QueryLogicNode(op="target", slot=target.slot, target_index=index)
        for index, target in enumerate(targets)
    )
    if len(leaves) == 1:
        return leaves[0]
    return QueryLogicNode(op="or", children=leaves)


def _logic_node_to_dict(node: QueryLogicNode | None, targets: tuple[QueryTarget, ...]) -> dict | None:
    if node is None:
        return None
    if node.op == "target":
        target = targets[node.target_index] if node.target_index is not None and node.target_index < len(targets) else None
        return {
            "op": "target",
            "slot": node.slot,
            "intent": target.intent if target else "",
        }
    return {
        "op": node.op,
        "children": [
            child
            for child in (_logic_node_to_dict(item, targets) for item in node.children)
            if child is not None
        ],
    }


def _analyze_query_with_llm(query: str) -> QueryAnalysis:
    fallback = _fallback_query_analysis(query)
    if not is_chat_provider_configured():
        return fallback

    try:
        llm = create_chat_llm(temperature=0)
        response = llm.invoke(
            [
                SystemMessage(content=QUERY_REWRITE_PROMPT),
                HumanMessage(content=query),
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        payload = _extract_json(content)
    except Exception:
        logger.exception("Failed to rewrite tag-search query with LLM")
        return fallback

    type_hint: Literal["art", "function", "mixed"] = "function"

    intent = " ".join(str(payload.get("intent", "")).split())
    core_concepts = _as_string_list(payload.get("core_concepts"), max_items=8)
    expanded_queries = _as_string_list(payload.get("expanded_queries"), max_items=12)
    excluded_concepts = _as_string_list(payload.get("excluded_concepts"), max_items=8)
    targets: list[QueryTarget] = []
    logic = _parse_logic_node(payload.get("logic"), targets)

    raw_targets = payload.get("targets", [])
    if logic is None and isinstance(raw_targets, list):
        for item in raw_targets[:8]:
            if not isinstance(item, dict):
                continue
            target = _target_from_payload(item, fallback_slot=f"target_{len(targets) + 1}")
            if target is None:
                continue
            targets.append(target)

    target_tuple = tuple(targets) or fallback.targets
    logic = logic or _logic_from_targets(target_tuple) or fallback.logic

    expansions = [query]
    if intent:
        expansions.append(intent)
    expansions.extend(core_concepts)
    expansions.extend(expanded_queries)
    expansions.extend(fallback.expansions)

    return QueryAnalysis(
        type_hint=type_hint,
        intent=intent or fallback.intent,
        expansions=tuple(dict.fromkeys(item for item in expansions if item)),
        excluded_concepts=tuple(dict.fromkeys(excluded_concepts)),
        rewrite_used=True,
        targets=target_tuple,
        logic=logic,
    )


def _build_query_terms(expansions: list[str]) -> tuple[set[str], list[str]]:
    tokens: set[str] = set()
    phrases: list[str] = []
    for item in expansions:
        normalized = _normalize(item)
        if not normalized:
            continue
        phrases.append(normalized)
        tokens.update(token for token in _tokenize(normalized) if len(token) >= 2)
    return tokens, phrases


def _score_entry(entry: TagEntry, query_tokens: set[str], phrases: list[str], type_hint: str) -> tuple[float, str]:
    semantic_tokens = entry.semantic_tokens or entry.tokens
    searchable_text = _normalize(
        " ".join(
            item
            for item in (
                entry.normalized,
                entry.embedding_text,
                " ".join(entry.aliases),
                " ".join(entry.retrieval_phrases),
                entry.description,
            )
            if item
        )
    )

    canonical_overlap = len(entry.tokens & query_tokens)
    semantic_overlap = len(semantic_tokens & query_tokens)
    overlap = canonical_overlap + max(0, semantic_overlap - canonical_overlap) * 0.55
    substring_hits = sum(1 for token in query_tokens if len(token) >= 3 and token in searchable_text)
    exact_hits = sum(1 for phrase in phrases if phrase and phrase == entry.normalized)
    phrase_hits = sum(1 for phrase in phrases if phrase and phrase != entry.normalized and phrase in searchable_text)

    score = overlap * 6.0 + substring_hits * 2.5 + exact_hits * 12.0 + phrase_hits * 4.0

    if type_hint == entry.tag_type:
        score += 1.5
    elif type_hint != "mixed":
        score -= 0.75

    if score <= 0:
        similarity = SequenceMatcher(None, " ".join(sorted(query_tokens)), entry.normalized).ratio()
        if similarity >= 0.58:
            score = similarity * 5.0

    if exact_hits:
        reason = "Exact concept match"
    elif canonical_overlap >= 2:
        reason = "Shares multiple query terms"
    elif canonical_overlap == 1 or substring_hits:
        reason = "Matches a key query term"
    elif phrase_hits:
        reason = "Matches an expanded concept"
    elif semantic_overlap:
        reason = "Matches cached semantic expansion"
    else:
        reason = "Semantic fallback match"

    return score, reason


def _build_search_targets(analysis: QueryAnalysis) -> tuple[QueryTarget, ...]:
    if analysis.targets:
        return analysis.targets
    return (
        QueryTarget(type_hint="function", intent=analysis.intent, expansions=analysis.expansions),
    )


def _single_tag_search_expr(tag_type: str, tag: str) -> str:
    return f"{tag_type}:{tag}"


def _score_entries_for_target(
    entries: tuple[TagEntry, ...],
    target: QueryTarget,
) -> tuple[list[dict], dict]:
    query_tokens, phrases = _build_query_terms(list(target.expansions))
    searchable_entries = tuple(entry for entry in entries if entry.tag_type == target.type_hint)
    scored: list[dict] = []

    for entry in searchable_entries:
        score, reason = _score_entry(entry, query_tokens, phrases, target.type_hint)
        if score <= 0:
            continue
        search_query = _single_tag_search_expr(entry.tag_type, entry.tag)
        scored.append(
            {
                "tag": entry.tag,
                "tag_type": entry.tag_type,
                "label": entry.label,
                "score": round(score, 3),
                "reason": reason,
                "search_query": search_query,
                "search_url": f"{SCRYFALL_SEARCH_URL}{quote(search_query)}",
                "target_type": target.type_hint,
                "target_intent": target.intent,
                "target_slot": target.slot,
                "retrieval_source": "lexical",
            }
        )

    scored.sort(key=lambda item: (-item["score"], item["tag_type"], item["tag"]))
    return scored, {
        "type": target.type_hint,
        "slot": target.slot,
        "intent": target.intent,
        "expanded_queries": list(target.expansions),
        "searched_tags": len(searchable_entries),
        "candidate_count": len(scored),
    }


def _target_embedding_query_text(target: QueryTarget) -> str:
    parts = [target.intent, *target.expansions]
    deduped = [item for item in dict.fromkeys(" ".join(part.split()) for part in parts if part)]
    return ". ".join(deduped)


async def _vector_search_entries_for_target(
    target: QueryTarget,
    *,
    limit: int = TAG_VECTOR_SEARCH_LIMIT,
) -> list[dict]:
    if target.type_hint != "function":
        return []

    query_text = _target_embedding_query_text(target)
    if not query_text:
        return []

    pool = await get_pool()
    try:
        has_embeddings = await pool.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM tagger_tags
                WHERE removed_at IS NULL
                  AND tag_type = 'function'
                  AND expansion_generated_at IS NOT NULL
                  AND embedding IS NOT NULL
            )
            """
        )
    except Exception as exc:
        logger.warning("Tag vector availability check failed; falling back to lexical tag search: %s", exc)
        return []
    if not has_embeddings:
        return []

    try:
        vectors = await asyncio.to_thread(encode_query, [query_text])
    except Exception as exc:
        logger.warning("Tag vector query embedding failed; falling back to lexical tag search: %s", exc)
        return []

    if not vectors:
        return []

    try:
        rows = await pool.fetch(
            """
            SELECT
                tag,
                tag_type,
                label,
                aliases,
                retrieval_phrases,
                description,
                embedding_text,
                embedding <=> $1::halfvec AS distance
            FROM tagger_tags
            WHERE removed_at IS NULL
              AND tag_type = 'function'
              AND expansion_generated_at IS NOT NULL
              AND embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT $2
            """,
            _vector_literal(vectors[0]),
            limit,
        )
    except Exception as exc:
        logger.warning("Tag vector search failed; falling back to lexical tag search: %s", exc)
        return []

    scored: list[dict] = []
    for row in rows:
        distance = float(row["distance"])
        search_query = _single_tag_search_expr(row["tag_type"], row["tag"])
        scored.append(
            {
                "tag": row["tag"],
                "tag_type": row["tag_type"],
                "label": row["label"],
                "score": round(1.0 - distance, 6),
                "reason": "Vector semantic match",
                "search_query": search_query,
                "search_url": f"{SCRYFALL_SEARCH_URL}{quote(search_query)}",
                "target_type": target.type_hint,
                "target_intent": target.intent,
                "target_slot": target.slot,
                "retrieval_source": "vector",
                "vector_distance": round(distance, 6),
                "aliases": _as_string_list(row["aliases"], max_items=5),
                "retrieval_phrases": _as_string_list(row["retrieval_phrases"], max_items=8),
                "description": row["description"] or "",
                "embedding_text": row["embedding_text"] or "",
            }
        )
    return scored


def _merge_target_candidates(target_results: list[list[dict]], per_target_limit: int = 24) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    for result in target_results:
        for rank, item in enumerate(result[:per_target_limit], start=1):
            key = (item["tag_type"], item["tag"])
            rrf_score = 1.0 / (RRF_K + rank)
            existing = merged.get(key)
            if existing is None:
                candidate = dict(item)
                candidate["score"] = rrf_score
                candidate["retrieval_sources"] = [item.get("retrieval_source", "unknown")]
                candidate["source_scores"] = {
                    item.get("retrieval_source", "unknown"): item.get("score", 0.0),
                    "best_raw_score": item.get("score", 0.0),
                }
                merged[key] = candidate
                continue

            existing["score"] += rrf_score
            source = item.get("retrieval_source", "unknown")
            if source not in existing["retrieval_sources"]:
                existing["retrieval_sources"].append(source)
            source_scores = existing.setdefault("source_scores", {})
            source_scores[source] = max(source_scores.get(source, float("-inf")), item.get("score", 0.0))
            if item.get("score", 0.0) > source_scores.get("best_raw_score", float("-inf")):
                existing["reason"] = item.get("reason", existing["reason"])
                source_scores["best_raw_score"] = item.get("score", 0.0)
    candidates = list(merged.values())
    candidates.sort(key=lambda item: (-item["score"], item["tag_type"], item["tag"]))
    return candidates


def _tag_search_expr(match: dict) -> str:
    return _single_tag_search_expr(match["tag_type"], match["tag"])


def _compose_flat_search_query(matches: list[dict]) -> list[str]:
    grouped: dict[str, list[str]] = {"art": [], "function": []}
    for match in matches:
        grouped[match["tag_type"]].append(match["tag"])

    queries: list[str] = []
    if grouped["art"]:
        queries.append(" or ".join(_single_tag_search_expr("art", tag) for tag in grouped["art"][:4]))
    if grouped["function"]:
        queries.append(" or ".join(_single_tag_search_expr("function", tag) for tag in grouped["function"][:4]))
    return queries


def _compose_logic_expr(node: QueryLogicNode, matches_by_slot: dict[str, list[dict]], *, top: bool = False) -> str:
    if node.op == "target":
        slot_matches = matches_by_slot.get(node.slot, [])[:4]
        if not slot_matches:
            return ""
        expr = " or ".join(_tag_search_expr(match) for match in slot_matches)
        return f"({expr})" if len(slot_matches) > 1 else expr

    child_exprs = [
        expr
        for expr in (_compose_logic_expr(child, matches_by_slot) for child in node.children)
        if expr
    ]
    if not child_exprs:
        return ""
    separator = " " if node.op == "and" else " or "
    expr = separator.join(child_exprs)
    if top or len(child_exprs) == 1:
        return expr
    return f"({expr})"


def _compose_search_query(matches: list[dict], logic: QueryLogicNode | None = None) -> list[str]:
    if logic is None:
        return _compose_flat_search_query(matches)

    matches_by_slot: dict[str, list[dict]] = {}
    for match in matches:
        slot = str(match.get("target_slot") or "").strip()
        if not slot:
            continue
        matches_by_slot.setdefault(slot, []).append(match)

    query = _compose_logic_expr(logic, matches_by_slot, top=True)
    if query:
        return [query]
    return _compose_flat_search_query(matches)


def _preserve_tag_effect_qualifiers(original_query: str, effect_query: str) -> str:
    original = _normalize(original_query)
    effect = " ".join(effect_query.split())
    effect_normalized = _normalize(effect)
    if not effect:
        return effect

    has_repeatability = bool(
        re.search(r"\brepeat(?:ly|edly|able|ing)?\b", original)
        or "each turn" in original
        or "every turn" in original
        or "whenever" in original
        or any(term in original_query for term in ("反复", "重复", "每回合", "每个回合", "每当"))
    )
    has_repeatability_in_effect = bool(
        re.search(r"\brepeat(?:ly|edly|able|ing)?\b", effect_normalized)
        or "each turn" in effect_normalized
        or "every turn" in effect_normalized
        or "whenever" in effect_normalized
    )
    mentions_token_creation = (
        "token" in original
        and any(verb in original for verb in ("create", "creates", "created", "make", "makes", "produce", "produces"))
    ) or (
        "token" in effect_normalized
        and any(verb in effect_normalized for verb in ("create", "creates", "created", "make", "makes", "produce", "produces"))
    )

    if has_repeatability and not has_repeatability_in_effect and mentions_token_creation:
        effect = re.sub(r"\bcreate a token\b", "repeatedly create tokens", effect, flags=re.IGNORECASE)
        effect = re.sub(r"\bcreates a token\b", "repeatedly creates tokens", effect, flags=re.IGNORECASE)
        effect = re.sub(r"\bcreate token\b", "repeatedly create tokens", effect, flags=re.IGNORECASE)
        effect = re.sub(r"\bcreates token\b", "repeatedly creates tokens", effect, flags=re.IGNORECASE)
        if "repeat" not in _normalize(effect):
            effect = f"repeatedly {effect}"

    return " ".join(effect.split())


def _evaluate_tag_logic(
    logic: QueryLogicNode | None,
    cards_by_slot: dict[str, set[str]],
    all_card_ids: set[str],
) -> set[str]:
    if logic is None:
        return set(all_card_ids)

    if logic.op == "target":
        return set(cards_by_slot.get(logic.slot, set()))

    child_sets = [
        _evaluate_tag_logic(child, cards_by_slot, all_card_ids)
        for child in logic.children
    ]
    if not child_sets:
        return set()

    if logic.op == "and":
        eligible = set(child_sets[0])
        for child_set in child_sets[1:]:
            eligible &= child_set
        return eligible

    eligible: set[str] = set()
    for child_set in child_sets:
        eligible |= child_set
    return eligible


async def _card_filters_for_tag_query(query: str) -> tuple[list[str] | None, dict]:
    started = time.perf_counter()
    try:
        constraints, tokens_prompt, tokens_completion = await asyncio.to_thread(
            extract_card_search_constraints,
            query,
        )
    except Exception as exc:
        logger.warning("Tag-search card constraint extraction failed: %s", exc)
        return None, {
            "card_filter_used": False,
            "card_filters": {},
            "card_filter_error": f"{type(exc).__name__}: {exc}",
        }

    tag_retrieval_query = _preserve_tag_effect_qualifiers(
        query,
        " ".join(str(constraints.get("oracle_text") or "").split()) or query,
    )
    logged_constraints = {
        key: value
        for key, value in constraints.items()
        if value and key not in ("oracle_text", "name")
    }
    if logged_constraints:
        logger.info("<<< AI Search parsed card filters: %s", logged_constraints)

    filters = build_structured_card_filters(constraints)
    meta = {
        "card_filter_used": bool(filters),
        "card_filters": filters,
        "card_filter_tokens_prompt": tokens_prompt,
        "card_filter_tokens_completion": tokens_completion,
        "tag_retrieval_query": tag_retrieval_query,
    }
    if not filters:
        logger.info("<<< AI Search no card filters, skipping structured filtering in %.2fs", time.perf_counter() - started)
        return None, meta

    filter_started = time.perf_counter()
    card_ids = await filter_cards(filters)
    meta["card_filter_count"] = len(card_ids)
    logger.info("<<< AI Search filtered to %d cards in %.2fs", len(card_ids), time.perf_counter() - filter_started)
    logger.info("<<< AI Search card filter extraction took %.2fs", time.perf_counter() - started)
    return card_ids, meta


async def _cards_for_tag_matches(
    matches: list[dict],
    *,
    logic: QueryLogicNode | None = None,
    filtered_card_ids: list[str] | None = None,
) -> list[dict]:
    started = time.perf_counter()
    function_matches = [
        match
        for match in matches
        if match.get("tag_type") == "function" and str(match.get("tag") or "").strip()
    ]
    if not function_matches:
        logger.info("<<< AI Search card lookup skipped: no function tag matches")
        return []
    if filtered_card_ids is not None and not filtered_card_ids:
        logger.info("<<< AI Search card lookup skipped: filters matched 0 cards")
        return []

    tags = [str(match["tag"]) for match in function_matches]
    scores = [float(match.get("score") or 0.0) for match in function_matches]
    ranks = list(range(1, len(function_matches) + 1))
    reasons = [str(match.get("reason") or "") for match in function_matches]
    labels = [str(match.get("label") or match.get("tag") or "") for match in function_matches]
    slots = [str(match.get("target_slot") or "target_1") for match in function_matches]

    pool = await get_pool()
    filter_clause = ""
    params: list = [tags, scores, ranks, reasons, labels, slots]
    if filtered_card_ids is not None:
        filter_clause = "AND ctt.card_id = ANY($7::text[])"
        params.append(filtered_card_ids)

    try:
        rows = await pool.fetch(
            f"""
            WITH selected AS (
                SELECT *
                FROM unnest(
                    $1::text[],
                    $2::float8[],
                    $3::int[],
                    $4::text[],
                    $5::text[],
                    $6::text[]
                ) AS item(tag, tag_score, tag_rank, reason, label, slot)
            )
            SELECT
                ctt.card_id,
                c.name,
                selected.tag,
                selected.tag_score,
                selected.tag_rank,
                selected.reason,
                selected.label,
                selected.slot
            FROM selected
            JOIN card_tagger_tags ctt
              ON ctt.tag_type = 'function'
             AND ctt.tag = selected.tag
             {filter_clause}
            JOIN cards c ON c.id = ctt.card_id
            """,
            *params,
        )
    except Exception as exc:
        logger.warning("Tag-card relation lookup failed; returning tag matches only: %s", exc)
        return []

    card_rows: dict[str, dict] = {}
    cards_by_slot: dict[str, set[str]] = {}
    for row in rows:
        card_id = row["card_id"]
        slot = str(row["slot"] or "target_1")
        cards_by_slot.setdefault(slot, set()).add(card_id)
        card = card_rows.setdefault(
            card_id,
            {
                "card_id": card_id,
                "name": row["name"] or "",
                "matched_tag_count": 0,
                "tag_score_sum": 0.0,
                "best_tag_rank": 10**9,
                "matched_tags": [],
            },
        )
        card["matched_tag_count"] += 1
        card["tag_score_sum"] += float(row["tag_score"] or 0.0)
        card["best_tag_rank"] = min(card["best_tag_rank"], int(row["tag_rank"] or 10**9))
        card["matched_tags"].append(
            {
                "tag": row["tag"],
                "tag_type": "function",
                "label": row["label"],
                "score": float(row["tag_score"] or 0.0),
                "reason": row["reason"],
                "slot": slot,
            }
        )

    all_card_ids = set(card_rows)
    eligible_card_ids = _evaluate_tag_logic(logic, cards_by_slot, all_card_ids)
    ranked = [
        item
        for item in card_rows.values()
        if item["card_id"] in eligible_card_ids
    ]
    ranked.sort(
        key=lambda item: (
            -int(item["matched_tag_count"]),
            -float(item["tag_score_sum"]),
            int(item["best_tag_rank"]),
            item["name"],
        )
    )

    card_ids = [item["card_id"] for item in ranked]
    cards = await get_cards_by_ids(card_ids)
    meta_by_id = {item["card_id"]: item for item in ranked}
    for card in cards:
        meta = meta_by_id.get(card.get("id"))
        if not meta:
            continue
        matched_tags = meta["matched_tags"]
        matched_tags.sort(key=lambda item: (-float(item.get("score") or 0.0), str(item.get("tag") or "")))
        card["_matched_tags"] = matched_tags or []
        card["_matched_tag_count"] = int(meta["matched_tag_count"] or 0)
        card["_tag_score"] = float(meta["tag_score_sum"] or 0.0)
    logger.info(
        "<<< AI Search card relation lookup returned %d cards from %d tag matches, eligible=%d/%d, logic=%s in %.2fs",
        len(cards),
        len(function_matches),
        len(eligible_card_ids),
        len(all_card_ids),
        logic.op if logic else "flat-or",
        time.perf_counter() - started,
    )
    return cards


def _ensure_target_coverage(
    chosen: list[dict],
    candidates: list[dict],
    targets: tuple[QueryTarget, ...],
    limit: int,
) -> list[dict]:
    if not targets or limit <= 0:
        return chosen[:limit]

    selected_keys = {(item["tag_type"], item["tag"]) for item in chosen}
    covered_slots = {str(item.get("target_slot") or "") for item in chosen}
    expanded = list(chosen)

    for target in targets:
        if target.slot in covered_slots:
            continue
        fallback = next(
            (
                item
                for item in candidates
                if item.get("target_slot") == target.slot
                and (item["tag_type"], item["tag"]) not in selected_keys
            ),
            None,
        )
        if fallback is None:
            continue
        if len(expanded) >= limit:
            slot_counts: dict[str, int] = {}
            for item in expanded:
                slot = str(item.get("target_slot") or "")
                slot_counts[slot] = slot_counts.get(slot, 0) + 1
            replace_index = next(
                (
                    index
                    for index in range(len(expanded) - 1, -1, -1)
                    if slot_counts.get(str(expanded[index].get("target_slot") or ""), 0) > 1
                ),
                -1,
            )
            if replace_index < 0:
                continue
            removed = expanded.pop(replace_index)
            selected_keys.discard((removed["tag_type"], removed["tag"]))
        expanded.append(fallback)
        selected_keys.add((fallback["tag_type"], fallback["tag"]))
        covered_slots.add(target.slot)

    return expanded[:limit]


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
    return json.loads(cleaned)


def _rerank_with_llm(query: str, candidates: list[dict], limit: int) -> tuple[list[dict], bool]:
    if not candidates or not is_chat_provider_configured():
        return candidates[:limit], False

    lines = []
    for idx, candidate in enumerate(candidates, start=1):
        slot = candidate.get("target_slot") or "target"
        lines.append(
            f'{idx}. [slot: {slot}] [{candidate["tag_type"]}] {candidate["tag"]} '
            f'(label: {candidate["label"]}; heuristic: {candidate["reason"]})'
        )

    llm = create_chat_llm(temperature=0)
    response = llm.invoke(
        [
            SystemMessage(content=TAG_SELECTION_PROMPT),
            HumanMessage(
                content=(
                    f"User query: {query}\n"
                    f"Select up to {limit} tags.\n"
                    "Candidates:\n"
                    + "\n".join(lines)
                )
            ),
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)

    try:
        payload = _extract_json(content)
    except Exception:
        logger.warning("Failed to parse tag-selection LLM response: %s", content)
        return candidates[:limit], False

    selected = payload.get("selected", [])
    chosen: list[dict] = []
    for item in selected:
        if not isinstance(item, dict):
            continue
        idx = item.get("id")
        if not isinstance(idx, int) or idx < 1 or idx > len(candidates):
            continue
        candidate = dict(candidates[idx - 1])
        reason = str(item.get("reason", "")).strip()
        if reason:
            candidate["reason"] = reason
        chosen.append(candidate)

    if not chosen:
        return candidates[:limit], False

    seen = set()
    deduped: list[dict] = []
    for candidate in chosen:
        key = (candidate["tag_type"], candidate["tag"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped[:limit], True


def _generate_expansion_batch(
    entries: list[TagEntry],
    sample_size: int = SAMPLE_CARDS_PER_TAG,
    scryfall_delay_seconds: float = SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS,
) -> dict[str, dict]:
    if not entries or not is_chat_provider_configured():
        return {}

    samples_by_key: dict[str, list[dict]] = {}
    for entry in entries:
        key = _tag_key(entry.tag_type, entry.tag)
        samples_by_key[key] = _fetch_sample_cards_for_tag(entry, sample_size)
        time.sleep(max(0.0, scryfall_delay_seconds))

    payload = {
        "tags": [
            {
                "key": _tag_key(entry.tag_type, entry.tag),
                "tag": entry.tag,
                "type": entry.tag_type,
                "label": entry.label,
                "sample_cards": samples_by_key.get(_tag_key(entry.tag_type, entry.tag), []),
            }
            for entry in entries
        ]
    }

    llm = create_chat_llm(temperature=0.2)
    response = llm.invoke(
        [
            SystemMessage(content=TAG_EXPANSION_PROMPT),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)
    try:
        data = _extract_json(content)
    except Exception:
        logger.warning("Failed to parse tag-expansion LLM response: %s", content)
        return {}

    items = data.get("items", [])
    if not isinstance(items, list):
        return {}

    entry_by_key = {_tag_key(entry.tag_type, entry.tag): entry for entry in entries}
    generated: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip()
        entry = entry_by_key.get(key)
        if entry is None:
            continue

        aliases = _as_string_list(item.get("aliases"), max_items=5)
        retrieval_phrases = _as_string_list(item.get("retrieval_phrases"), max_items=8)
        description = " ".join(str(item.get("description", "")).split())
        embedding_text = _build_embedding_text(
            entry.tag,
            entry.tag_type,
            entry.label,
            aliases,
            retrieval_phrases,
            description,
        )
        generated[key] = {
            "tag": entry.tag,
            "tag_type": entry.tag_type,
            "label": entry.label,
            "aliases": aliases,
            "retrieval_phrases": retrieval_phrases,
            "description": description,
            "embedding_text": embedding_text,
            "sample_cards": samples_by_key.get(key, []),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": "deepseek",
        }
    return generated


async def build_tag_expansion_cache(
    *,
    limit: int | None = None,
    batch_size: int = 10,
    force: bool = False,
    tag_types: set[str] | None = None,
    sample_size: int = SAMPLE_CARDS_PER_TAG,
    scryfall_delay_seconds: float = SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS,
    print_embedding_text: bool = False,
    write_json_cache: bool = False,
) -> dict:
    snapshot = await catalog_store.get_snapshot()
    payload: dict | None = None
    items: dict[str, dict] = {}
    if write_json_cache:
        payload = _read_tag_expansion_payload()
        payload["version"] = TAG_EXPANSION_CACHE_VERSION
        payload["source_url"] = TAGGER_TAGS_URL
        payload["source_content_hash"] = snapshot.content_hash
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        items = payload.setdefault("items", {})
        items.update(await _load_generated_expansion_items_from_db())
    pending, existing_count = await _load_expansion_work_from_db(
        limit=limit,
        force=force,
        tag_types=tag_types,
    )

    if limit is not None and limit <= 0:
        return {
            "status": "ok",
            "cache_path": str(TAG_EXPANSION_CACHE_PATH) if write_json_cache else None,
            "total_tags": len(snapshot.entries),
            "existing_items": existing_count,
            "source_of_truth": "database",
            "write_json_cache": write_json_cache,
            "pending_selected": 0,
            "generated": 0,
            "failed_batches": 0,
            "sample_size": sample_size,
            "scryfall_delay_seconds": scryfall_delay_seconds,
            "print_embedding_text": print_embedding_text,
        }

    generated_count = 0
    failed_batches = 0
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset : offset + batch_size]
        generated = await asyncio.to_thread(
            _generate_expansion_batch,
            batch,
            sample_size,
            scryfall_delay_seconds,
        )
        if not generated:
            failed_batches += 1
            continue
        await _persist_generated_expansions(generated)
        if write_json_cache and payload is not None:
            items.update(generated)
            _write_tag_expansion_payload(payload)
        if print_embedding_text:
            for item in generated.values():
                print(
                    f"[embedding_text] {item['tag_type']}:{item['tag']} -> {item['embedding_text']}",
                    flush=True,
                )
        generated_count += len(generated)

    if write_json_cache and payload is not None:
        _write_tag_expansion_payload(payload)
    return {
        "status": "ok",
        "cache_path": str(TAG_EXPANSION_CACHE_PATH) if write_json_cache else None,
        "total_tags": len(snapshot.entries),
        "existing_items": existing_count,
        "source_of_truth": "database",
        "write_json_cache": write_json_cache,
        "pending_selected": len(pending),
        "generated": generated_count,
        "failed_batches": failed_batches,
        "sample_size": sample_size,
        "scryfall_delay_seconds": scryfall_delay_seconds,
        "print_embedding_text": print_embedding_text,
    }


async def generate_missing_tag_embeddings(
    *,
    limit: int = 500,
    batch_size: int = 64,
    force: bool = False,
    print_embedding_text: bool = False,
) -> dict:
    pool = await get_pool()
    await pool.execute("ALTER TABLE tagger_tags ADD COLUMN IF NOT EXISTS embedding halfvec(2560)")
    await pool.execute("ALTER TABLE tagger_tags ADD COLUMN IF NOT EXISTS expansion_generated_at TIMESTAMPTZ")

    where = (
        "removed_at IS NULL AND tag_type = 'function' "
        "AND embedding_text <> '' AND expansion_generated_at IS NOT NULL"
    )
    if not force:
        where += " AND embedding IS NULL"

    rows = await pool.fetch(
        f"""
        SELECT tag_type, tag, embedding_text
        FROM tagger_tags
        WHERE {where}
        ORDER BY tag
        LIMIT $1
        """,
        limit,
    )

    processed = 0
    failed_batches = 0
    for offset in range(0, len(rows), batch_size):
        batch = rows[offset : offset + batch_size]
        texts = [row["embedding_text"] for row in batch]
        if print_embedding_text:
            for row in batch:
                logger.info("[tag-embedding-text] %s:%s -> %s", row["tag_type"], row["tag"], row["embedding_text"])

        vectors = await asyncio.to_thread(encode_batch_safe, texts)
        if vectors is None:
            failed_batches += 1
            continue

        await pool.executemany(
            """
            UPDATE tagger_tags
            SET embedding = $1::halfvec
            WHERE tag_type = $2 AND tag = $3
            """,
            [
                (_vector_literal(vector), row["tag_type"], row["tag"])
                for row, vector in zip(batch, vectors)
            ],
        )
        processed += len(batch)

    return {
        "status": "ok",
        "selected": len(rows),
        "processed": processed,
        "failed_batches": failed_batches,
    }


async def search_tags(query: str, limit: int = 12) -> dict:
    started = time.perf_counter()
    query = query.strip()
    if not query:
        raise ValueError("Query must not be empty")

    logger.info(">>> AI Search query: %s", query)
    snapshot_task = asyncio.create_task(catalog_store.get_snapshot())
    card_filter_task = asyncio.create_task(_card_filters_for_tag_query(query))

    snapshot = await snapshot_task
    filtered_card_ids, card_filter_meta = await card_filter_task
    tag_retrieval_query = str(card_filter_meta.get("tag_retrieval_query") or query).strip() or query
    if tag_retrieval_query != query:
        logger.info("<<< AI Search effect query after filters: %s", tag_retrieval_query)
    analysis = await asyncio.to_thread(_analyze_query_with_llm, tag_retrieval_query)
    logger.info(
        "<<< AI Search analysis: type_hint=%s rewrite=%s intent=%r targets=%d excluded=%s",
        analysis.type_hint,
        analysis.rewrite_used,
        analysis.intent,
        len(analysis.targets),
        list(analysis.excluded_concepts),
    )
    targets = _build_search_targets(analysis)
    logger.info("<<< AI Search retrieval targets: %s", [target.intent for target in targets])
    target_results: list[list[dict]] = []
    target_meta: list[dict] = []
    for target in targets:
        target_started = time.perf_counter()
        lexical_scored, meta = _score_entries_for_target(snapshot.entries, target)
        vector_scored = await _vector_search_entries_for_target(target)
        target_results.append(vector_scored)
        target_results.append(lexical_scored)
        unique_candidates = {
            (item["tag_type"], item["tag"])
            for result in (vector_scored, lexical_scored)
            for item in result
        }
        meta["vector_candidate_count"] = len(vector_scored)
        meta["lexical_candidate_count"] = len(lexical_scored)
        meta["candidate_count"] = len(unique_candidates)
        target_meta.append(meta)
        logger.info(
            "  AI Search target [%s:%s]: lexical=%d vector=%d unique=%d in %.2fs",
            target.slot,
            target.type_hint,
            len(lexical_scored),
            len(vector_scored),
            len(unique_candidates),
            time.perf_counter() - target_started,
        )

    candidates = _merge_target_candidates(target_results)[:40]
    logger.info("<<< AI Search merged candidates: %d", len(candidates))
    rerank_query = analysis.intent or query
    if target_meta:
        target_summary = "; ".join(
            f'{item["slot"]}={item["intent"]}' for item in target_meta if item.get("intent")
        )
        if target_summary:
            rerank_query = f"{rerank_query}. Retrieval targets: {target_summary}"
    if analysis.excluded_concepts:
        rerank_query = f"{rerank_query}. Exclude: {', '.join(analysis.excluded_concepts)}"
    rerank_started = time.perf_counter()
    chosen, llm_used = await asyncio.to_thread(_rerank_with_llm, rerank_query, candidates, limit)
    chosen = _ensure_target_coverage(chosen, candidates, targets, limit)
    logger.info(
        "<<< AI Search rerank selected %d tags from %d candidates, llm_used=%s in %.2fs",
        len(chosen),
        len(candidates),
        llm_used,
        time.perf_counter() - rerank_started,
    )
    for index, match in enumerate(chosen[:limit], start=1):
        logger.info(
            "  AI Search selected [%d] %s:%s score=%.4f reason=%s",
            index,
            match.get("tag_type"),
            match.get("tag"),
            float(match.get("score") or 0.0),
            match.get("reason"),
        )
    cards = await _cards_for_tag_matches(
        chosen,
        logic=analysis.logic,
        filtered_card_ids=filtered_card_ids,
    )
    logger.info(
        "<<< AI Search final: %d cards, filters_used=%s, total took %.2fs",
        len(cards),
        card_filter_meta.get("card_filter_used"),
        time.perf_counter() - started,
    )

    total_tags = len(snapshot.entries)
    art_tags = sum(1 for entry in snapshot.entries if entry.tag_type == "art")
    function_tags = total_tags - art_tags

    return {
        "query": query,
        "suggested_queries": _compose_search_query(chosen, analysis.logic),
        "matches": chosen[:limit],
        "cards": cards,
        "catalog": {
            "total_tags": total_tags,
            "art_tags": art_tags,
            "function_tags": function_tags,
            "card_count": len(cards),
            **card_filter_meta,
            "searched_tags": sum(item["searched_tags"] for item in target_meta),
            "etag": snapshot.etag,
            "loaded_at": snapshot.loaded_at,
            "checked_at": snapshot.checked_at,
            "llm_used": llm_used,
            "query_rewrite_used": analysis.rewrite_used,
            "rewritten_intent": analysis.intent,
            "type_hint": analysis.type_hint,
            "targets": target_meta,
            "logic": _logic_node_to_dict(analysis.logic, targets),
        },
    }
