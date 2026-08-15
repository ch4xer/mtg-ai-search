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

from html import unescape
from typing import Literal
from urllib.parse import quote

import httpx
from langchain_core.messages import HumanMessage, SystemMessage

from ..embedding import encode_batch_or_none, encode_queries
from ..llm_provider import create_chat_llm, is_chat_provider_configured
from ..repositories.cards import get_cards_by_ids
from ..repositories.database import get_pool
from .card_query_constraints import build_structured_card_filters, extract_card_search_constraints
from .llm_json import parse_llm_json_object

from app.config import USER_AGENT

logger = logging.getLogger(__name__)

TAGGER_TAGS_URL = "https://scryfall.com/docs/tagger-tags"
SCRYFALL_SEARCH_URL = "https://scryfall.com/search?q="
SCRYFALL_API_CARDS_SEARCH_URL = "https://api.scryfall.com/cards/search"
REFRESH_INTERVAL = timedelta(hours=12)
SAMPLE_CARDS_PER_TAG = 3
SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS = float(os.getenv("SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS", "0.35"))
TAG_EXPANSION_DB_VERSION = 1
TAG_VECTOR_SEARCH_LIMIT = 40

RERANK_SKIP_LEAD_RATIO = float(os.getenv("AI_SEARCH_RERANK_SKIP_LEAD_RATIO", "1.45"))
RERANK_SKIP_MIN_GAP = float(os.getenv("AI_SEARCH_RERANK_SKIP_MIN_GAP", "0.006"))

SUPPORTED_TAG_TYPES: set[Literal["function"]] = {"function"}

TAG_RERANK_PROMPT = (
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
    intent: str
    expansions: tuple[str, ...]
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
        "q": _single_tag_search_expr(tag),
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
    target_intent = " ".join(str(item.get("intent", "")).split())
    if not target_intent:
        return None

    return QueryTarget(
        intent=target_intent,
        expansions=(target_intent,),
        slot=_sanitize_slot(item.get("slot"), fallback_slot),
    )


def _target_index_by_slot(targets: list[QueryTarget], slot: str) -> int | None:
    for index, target in enumerate(targets):
        if target.slot == slot:
            return index
    return None


def _parse_logic_node(
    value: object,
    targets: list[QueryTarget],
    *,
    path: str = "target",
) -> QueryLogicNode | None:
    if isinstance(value, str):
        slot = _sanitize_slot(value, f"{path}_{len(targets) + 1}")
        return QueryLogicNode(op="target", slot=slot, target_index=_target_index_by_slot(targets, slot))

    if not isinstance(value, dict):
        return None

    op = str(value.get("op", "")).strip().lower()
    if op == "target":
        slot = _sanitize_slot(value.get("slot"), f"{path}_{len(targets) + 1}")
        return QueryLogicNode(op="target", slot=slot, target_index=_target_index_by_slot(targets, slot))

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
        return node.slot
    return {
        "op": node.op,
        "children": [
            child
            for child in (_logic_node_to_dict(item, targets) for item in node.children)
            if child is not None
        ],
    }


def _logic_node_from_plan(value: object) -> QueryLogicNode | None:
    if isinstance(value, str):
        return QueryLogicNode(op="target", slot=_sanitize_slot(value, "target_1"))

    if not isinstance(value, dict):
        return None

    op = str(value.get("op", "")).strip().lower()
    if op == "target":
        slot = _sanitize_slot(value.get("slot"), "target_1")
        return QueryLogicNode(op="target", slot=slot)

    if op not in {"and", "or"}:
        return None

    raw_children = value.get("children", [])
    if not isinstance(raw_children, list):
        return None
    children = tuple(
        child
        for child in (_logic_node_from_plan(item) for item in raw_children[:8])
        if child is not None
    )
    if not children:
        return None
    if len(children) == 1:
        return children[0]
    return QueryLogicNode(op=op, children=children)


def _clean_plan_query_part(value: object) -> str:
    return " ".join(str(value or "").split()).strip(" .")


def _collect_plan_target_intents(value: object, output: list[str]) -> None:
    if not isinstance(value, dict):
        return

    op = str(value.get("op", "")).strip().lower()
    if op in {"and", "or"}:
        children = value.get("children", [])
        if isinstance(children, list):
            for child in children[:8]:
                _collect_plan_target_intents(child, output)
        return

    intent = _clean_plan_query_part(value.get("intent"))
    if intent:
        output.append(intent)


def _tag_retrieval_query_from_plan(plan: dict) -> str:
    parts: list[str] = []
    raw_targets = plan.get("targets", [])
    if isinstance(raw_targets, list):
        for item in raw_targets[:8]:
            _collect_plan_target_intents(item, parts)
    _collect_plan_target_intents(plan.get("logic"), parts)

    return ". ".join(dict.fromkeys(item for item in parts if item))


def _analysis_from_search_plan(query: str, plan: dict, tag_retrieval_query: str) -> QueryAnalysis:
    targets: list[QueryTarget] = []
    raw_targets = plan.get("targets", [])
    if isinstance(raw_targets, list):
        for item in raw_targets[:8]:
            if not isinstance(item, dict):
                continue
            target = _target_from_payload(item, fallback_slot=f"target_{len(targets) + 1}")
            if target is None:
                continue
            targets.append(target)
    logic = _parse_logic_node(plan.get("logic"), targets)

    if not tag_retrieval_query:
        tag_retrieval_query = ". ".join(
            dict.fromkeys(_clean_plan_query_part(item.intent) for item in targets if item.intent)
        )

    if not tag_retrieval_query and not targets:
        return QueryAnalysis(
            intent="",
            expansions=(),
            targets=(),
            logic=None,
        )

    target_tuple = tuple(targets)
    logic = logic or _logic_from_targets(target_tuple)

    return QueryAnalysis(
        intent=tag_retrieval_query,
        expansions=(tag_retrieval_query,) if tag_retrieval_query else (),
        targets=target_tuple,
        logic=logic,
    )




def _build_search_targets(analysis: QueryAnalysis) -> tuple[QueryTarget, ...]:
    if analysis.targets:
        return analysis.targets
    return (
        QueryTarget(intent=analysis.intent, expansions=analysis.expansions),
    )


def _single_tag_search_expr(tag: str) -> str:
    return f"function:{tag}"


def _target_embedding_query_text(target: QueryTarget) -> str:
    parts = [target.intent, *target.expansions]
    deduped = [item for item in dict.fromkeys(" ".join(part.split()) for part in parts if part)]
    return ". ".join(deduped)


async def _vector_search_entries_for_target(
    target: QueryTarget,
    *,
    limit: int = TAG_VECTOR_SEARCH_LIMIT,
) -> list[dict]:
    results = await _vector_search_entries_for_targets((target,), limit=limit)
    return results[0] if results else []


async def _vector_search_entries_for_targets(
    targets: tuple[QueryTarget, ...],
    *,
    limit: int = TAG_VECTOR_SEARCH_LIMIT,
) -> list[list[dict]]:
    results: list[list[dict]] = [[] for _ in targets]
    indexed_queries: list[tuple[int, QueryTarget, str]] = []
    for index, target in enumerate(targets):
        query_text = _target_embedding_query_text(target)
        if not query_text:
            continue

        indexed_queries.append((index, target, query_text))

    if not indexed_queries:
        return results

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
        logger.warning("Tag vector availability check failed: %s", exc)
        return results
    if not has_embeddings:
        return results

    unique_query_texts = list(dict.fromkeys(query_text for _, _, query_text in indexed_queries))
    try:
        vectors = await asyncio.to_thread(encode_queries, unique_query_texts)
    except Exception as exc:
        logger.warning("Tag vector query embedding failed: %s", exc)
        return results

    if not vectors:
        return results

    vector_by_query_text = dict(zip(unique_query_texts, vectors))

    async def fetch_target_matches(index: int, target: QueryTarget, query_text: str) -> tuple[int, list[dict]]:
        vector = vector_by_query_text.get(query_text)
        if vector is None:
            return index, []
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
                _vector_literal(vector),
                limit,
            )
        except Exception as exc:
            logger.warning(
                "Tag vector search failed for target %s: %s",
                target.slot,
                exc,
            )
            return index, []

        scored: list[dict] = []
        for row in rows:
            distance = float(row["distance"])
            search_query = _single_tag_search_expr(row["tag"])
            scored.append(
                {
                    "tag": row["tag"],
                    "label": row["label"],
                    "score": round(1.0 - distance, 6),
                    "reason": "Vector semantic match",
                    "search_query": search_query,
                    "search_url": f"{SCRYFALL_SEARCH_URL}{quote(search_query)}",
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
        return index, scored

    fetched = await asyncio.gather(
        *(fetch_target_matches(index, target, query_text) for index, target, query_text in indexed_queries)
    )
    for index, scored in fetched:
        results[index] = scored
    return results


def _tag_search_expr(match: dict) -> str:
    return _single_tag_search_expr(match["tag"])


def _compose_flat_search_query(matches: list[dict]) -> list[str]:
    tags = [match["tag"] for match in matches if match.get("tag")]
    if not tags:
        return []
    return [" or ".join(_single_tag_search_expr(tag) for tag in tags[:4])]


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


def _parse_filter_condition(expr: str) -> tuple[str, str]:
    match = re.match(r"^(>=|<=|>|<|=)\s*(.+)$", str(expr or "").strip())
    if not match:
        return "=", str(expr or "").strip()
    return match.group(1), match.group(2).strip()


def _parse_color_filter(value: str) -> tuple[str, list[str]]:
    raw = str(value or "").strip()
    if raw.startswith("="):
        raw = raw[1:].strip()
        return "exact", raw.split()
    if raw.lower().startswith("any:"):
        raw = raw[4:].strip()
        return "any", raw.split()
    return "all", raw.split()


def _color_filter_column(key: str, card_alias: str) -> str:
    return f"{card_alias}.colors"


def _append_structured_filter_clause(
    clauses: list[str],
    params: list,
    key: str,
    value: object,
    *,
    card_alias: str,
) -> None:
    idx = len(params) + 1
    if key == "colors":
        column = _color_filter_column(key, card_alias)
        mode, symbols = _parse_color_filter(str(value or ""))
        if not symbols:
            return
        operator = "&&" if mode == "any" else "@>"
        clauses.append(f"COALESCE({column}, ARRAY[]::text[]) {operator} ${idx}::text[]")
        params.append(symbols)
        if mode == "exact":
            clauses.append(f"cardinality(COALESCE({column}, ARRAY[]::text[])) = ${len(params) + 1}")
            params.append(len(symbols))
        return

    if key == "excluded_colors":
        column = _color_filter_column(key.removeprefix("excluded_"), card_alias)
        _, symbols = _parse_color_filter(str(value or ""))
        if not symbols:
            return
        clauses.append(f"NOT (COALESCE({column}, ARRAY[]::text[]) && ${idx}::text[])")
        params.append(symbols)
        return

    if key == "type":
        for word in str(value or "").split():
            clauses.append(f"{card_alias}.type_line ILIKE ${len(params) + 1}")
            params.append(f"%{word}%")
        return

    if key == "layout":
        clauses.append(f"{card_alias}.layout = ${idx}")
        params.append(value)
        return

    if key not in ("cmc", "power", "toughness", "released_at"):
        return

    op, val = _parse_filter_condition(str(value or ""))
    if not val:
        return
    idx = len(params) + 1
    if key == "cmc":
        clauses.append(f"{card_alias}.cmc {op} ${idx}::real")
        params.append(float(val))
    elif key in ("power", "toughness"):
        clauses.append(
            f"{card_alias}.{key} ~ '^[0-9]+\\.?[0-9]*$' "
            f"AND CAST({card_alias}.{key} AS real) {op} ${idx}::real"
        )
        params.append(float(val))
    elif key == "released_at":
        from datetime import date as date_type

        clauses.append(
            "EXISTS ("
            "SELECT 1 FROM card_prints cp_filter "
            f"WHERE cp_filter.card_id = {card_alias}.id "
            f"AND cp_filter.released_at {op} ${idx}::date"
            ")"
        )
        params.append(date_type.fromisoformat(val))

def _build_structured_filter_where(filters: dict | None, params: list, *, card_alias: str = "c") -> str:
    if not filters:
        return ""

    clauses = [f"NOT COALESCE({card_alias}.is_unofficial, FALSE)"]
    for key, value in filters.items():
        if value is None or value == "":
            continue
        _append_structured_filter_clause(clauses, params, key, value, card_alias=card_alias)
    return " AND ".join(clauses)


async def _card_filters_for_tag_query(query: str) -> tuple[dict, dict, QueryAnalysis]:
    started = time.perf_counter()
    constraints, tokens_prompt, tokens_completion = await asyncio.to_thread(
        extract_card_search_constraints,
        query,
    )

    tag_retrieval_query = _tag_retrieval_query_from_plan(constraints)
    analysis = _analysis_from_search_plan(query, constraints, tag_retrieval_query)
    logged_constraints = {
        key: value
        for key, value in constraints.items()
        if value and key not in {"targets", "logic"}
    }
    filters = build_structured_card_filters(constraints)
    meta = {
        "card_filter_used": bool(filters),
        "card_filters": filters,
        "card_filter_tokens_prompt": tokens_prompt,
        "card_filter_tokens_completion": tokens_completion,
        "card_filter_plan_llm_used": True,
        "tag_retrieval_query": tag_retrieval_query,
    }
    if logged_constraints:
        logger.info("<<< AI Search card filters: %s (%.2fs)", logged_constraints, time.perf_counter() - started)
    return filters, meta, analysis


async def _cards_for_tag_matches(
    matches: list[dict],
    *,
    logic: QueryLogicNode | None = None,
    filtered_card_ids: list[str] | None = None,
    card_filters: dict | None = None,
    card_limit: int | None = None,
    card_offset: int = 0,
) -> dict:
    started = time.perf_counter()
    function_matches = [match for match in matches if str(match.get("tag") or "").strip()]
    if not function_matches:
        logger.info("<<< AI Search card lookup skipped: no tag matches")
        return {"cards": [], "total": 0}
    if filtered_card_ids is not None and not filtered_card_ids:
        logger.info("<<< AI Search card lookup skipped: filters matched 0 cards")
        return {"cards": [], "total": 0}

    tags = [str(match["tag"]) for match in function_matches]
    scores = [float(match.get("score") or 0.0) for match in function_matches]
    ranks = list(range(1, len(function_matches) + 1))
    reasons = [str(match.get("reason") or "") for match in function_matches]
    labels = [str(match.get("label") or match.get("tag") or "") for match in function_matches]
    slots = [str(match.get("target_slot") or "target_1") for match in function_matches]

    pool = await get_pool()
    ctt_filter_clause = ""
    card_filter_clause = ""
    params: list = [tags, scores, ranks, reasons, labels, slots]
    if filtered_card_ids is not None:
        ctt_filter_clause = "AND ctt.card_id = ANY($7::text[])"
        params.append(filtered_card_ids)
    structured_where = _build_structured_filter_where(card_filters, params, card_alias="c")
    if structured_where:
        card_filter_clause = f"WHERE {structured_where}"
    having_clause = _logic_to_sql_having(logic, params)
    limit_clause = ""
    if card_limit is not None:
        params.append(max(0, card_limit))
        limit_clause = f"LIMIT ${len(params)}"
    offset_clause = ""
    if card_offset > 0:
        params.append(max(0, card_offset))
        offset_clause = f"OFFSET ${len(params)}"

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
            ),
            matched AS (
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
                 {ctt_filter_clause}
                JOIN cards c ON c.id = ctt.card_id
                {card_filter_clause}
            ),
            aggregated AS (
                SELECT
                    card_id,
                    name,
                    COUNT(*) AS matched_tag_count,
                    SUM(tag_score) AS tag_score_sum,
                    MIN(tag_rank) AS best_tag_rank,
                    jsonb_agg(
                        jsonb_build_object(
                            'tag', tag,
                            'tag_type', 'function',
                            'label', label,
                            'score', tag_score,
                            'reason', reason,
                            'slot', slot
                        )
                        ORDER BY tag_score DESC, tag
                    ) AS matched_tags
                FROM matched
                GROUP BY card_id, name
                HAVING {having_clause}
            ),
            ranked AS (
                SELECT
                    *,
                    COUNT(*) OVER () AS total_ranked
                FROM aggregated
                ORDER BY
                    matched_tag_count DESC,
                    tag_score_sum DESC,
                    best_tag_rank ASC,
                    name ASC
                {limit_clause}
                {offset_clause}
            )
            SELECT
                card_id,
                matched_tag_count,
                tag_score_sum,
                matched_tags,
                total_ranked
            FROM ranked
            """,
            *params,
        )
    except Exception as exc:
        logger.warning("Tag-card relation lookup failed; returning tag matches only: %s", exc)
        return {"cards": [], "total": 0}

    ranked = [dict(row) for row in rows]
    total_ranked = int(ranked[0]["total_ranked"] or 0) if ranked else 0
    card_ids = [item["card_id"] for item in ranked]
    cards = await get_cards_by_ids(card_ids)
    meta_by_id = {item["card_id"]: item for item in ranked}
    for card in cards:
        meta = meta_by_id.get(card.get("id"))
        if not meta:
            continue
        matched_tags = _as_json_list(meta.get("matched_tags"))
        card["_matched_tags"] = matched_tags
        card["_matched_tag_count"] = int(meta["matched_tag_count"] or 0)
        card["_tag_score"] = float(meta["tag_score_sum"] or 0.0)
    logger.info(
        "<<< AI Search card relation lookup returned %d/%d cards from %d tag matches, offset=%d, logic=%s in %.2fs",
        len(cards),
        total_ranked,
        len(function_matches),
        card_offset,
        logic.op if logic else "flat-or",
        time.perf_counter() - started,
    )
    return {"cards": cards, "total": total_ranked}


async def _cards_for_structured_filters(
    card_filters: dict,
    *,
    card_limit: int | None = 60,
    card_offset: int = 0,
) -> dict:
    started = time.perf_counter()
    params: list = []
    where = _build_structured_filter_where(card_filters, params, card_alias="c")
    if not where:
        logger.info("<<< AI Search structured card lookup skipped: no structured filters")
        return {"cards": [], "total": 0}

    pool = await get_pool()
    try:
        total = await pool.fetchval(
            f"""
            SELECT COUNT(*)
            FROM cards c
            WHERE {where}
            """,
            *params,
        )

        page_params = list(params)
        limit_clause = ""
        if card_limit is not None:
            page_params.append(max(0, card_limit))
            limit_clause = f"LIMIT ${len(page_params)}"
        offset_clause = ""
        if card_offset > 0:
            page_params.append(max(0, card_offset))
            offset_clause = f"OFFSET ${len(page_params)}"

        rows = await pool.fetch(
            f"""
            SELECT c.id
            FROM cards c
            WHERE {where}
            ORDER BY c.name ASC
            {limit_clause}
            {offset_clause}
            """,
            *page_params,
        )
    except Exception as exc:
        logger.warning("Structured card lookup failed: %s", exc)
        return {"cards": [], "total": 0}

    card_ids = [row["id"] for row in rows]
    cards = await get_cards_by_ids(card_ids)
    total_cards = int(total or 0)
    logger.info(
        "<<< AI Search structured card lookup returned %d/%d cards, offset=%d in %.2fs",
        len(cards),
        total_cards,
        card_offset,
        time.perf_counter() - started,
    )
    return {"cards": cards, "total": total_cards}


def _plan_matches(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _plan_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


async def search_tags_from_plan(
    query: str,
    plan: dict,
    *,
    card_limit: int | None = 60,
    card_offset: int = 0,
) -> dict:
    started = time.perf_counter()
    if plan.get("mode") == "structured_filters":
        card_filters = dict(plan.get("card_filters") or {})
        card_result = await _cards_for_structured_filters(
            card_filters,
            card_limit=card_limit,
            card_offset=card_offset,
        )
        cards = card_result["cards"]
        total_cards = int(card_result["total"] or 0)
        catalog = dict(plan.get("catalog") if isinstance(plan.get("catalog"), dict) else {})
        catalog.update(
            {
                "card_count": len(cards),
                "total_card_count": total_cards,
                "card_limit": card_limit,
                "card_offset": max(0, card_offset),
                "search_session_hit": True,
            }
        )
        logger.info(
            "<<< AI Search structured session page: %d/%d cards, offset=%d, total took %.2fs",
            len(cards),
            total_cards,
            card_offset,
            time.perf_counter() - started,
        )
        return {
            "query": query,
            "suggested_queries": _plan_string_list(plan.get("suggested_queries")),
            "matches": [],
            "cards": cards,
            "catalog": catalog,
        }

    chosen = _plan_matches(plan.get("chosen"))
    logic = _logic_node_from_plan(plan.get("logic"))
    raw_filtered_card_ids = plan.get("filtered_card_ids")
    filtered_card_ids = _plan_string_list(raw_filtered_card_ids) if raw_filtered_card_ids is not None else None
    card_filters = dict(plan.get("card_filters") or {})

    card_result = await _cards_for_tag_matches(
        chosen,
        logic=logic,
        filtered_card_ids=filtered_card_ids,
        card_filters=card_filters,
        card_limit=card_limit,
        card_offset=card_offset,
    )
    cards = card_result["cards"]
    total_cards = int(card_result["total"] or 0)
    catalog = dict(plan.get("catalog") if isinstance(plan.get("catalog"), dict) else {})
    catalog.update(
        {
            "card_count": len(cards),
            "total_card_count": total_cards,
            "card_limit": card_limit,
            "card_offset": max(0, card_offset),
            "search_session_hit": True,
        }
    )
    logger.info(
        "<<< AI Search session page: %d/%d cards, offset=%d, total took %.2fs",
        len(cards),
        total_cards,
        card_offset,
        time.perf_counter() - started,
    )
    return {
        "query": query,
        "suggested_queries": _plan_string_list(plan.get("suggested_queries")),
        "matches": chosen[: int(plan.get("tag_limit") or len(chosen))],
        "cards": cards,
        "catalog": catalog,
    }


def _logic_to_sql_having(node: QueryLogicNode | None, params: list) -> str:
    if node is None:
        return "TRUE"

    if node.op == "target":
        params.append(node.slot)
        return f"bool_or(slot = ${len(params)})"

    child_exprs = [_logic_to_sql_having(child, params) for child in node.children]
    child_exprs = [expr for expr in child_exprs if expr]
    if not child_exprs:
        return "TRUE"

    separator = " AND " if node.op == "and" else " OR "
    return "(" + separator.join(child_exprs) + ")"


def _as_json_list(value) -> list:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    if isinstance(value, list):
        return value
    return []


def _ensure_target_coverage(
    chosen: list[dict],
    candidates: list[dict],
    targets: tuple[QueryTarget, ...],
    limit: int,
) -> list[dict]:
    if not targets or limit <= 0:
        return chosen[:limit]

    selected_keys = {item["tag"] for item in chosen}
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
                and item["tag"] not in selected_keys
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
            selected_keys.discard(removed["tag"])
        expanded.append(fallback)
        selected_keys.add(fallback["tag"])
        covered_slots.add(target.slot)

    return expanded[:limit]


def _extract_json(text: str) -> dict:
    return parse_llm_json_object(text)


def _score_has_clear_lead(first: dict, second: dict | None) -> bool:
    if second is None:
        return True
    first_score = float(first.get("score") or 0.0)
    second_score = float(second.get("score") or 0.0)
    if first_score <= 0:
        return False
    if second_score <= 0:
        return True
    return (
        first_score >= second_score * RERANK_SKIP_LEAD_RATIO
        and first_score - second_score >= RERANK_SKIP_MIN_GAP
    )


def _select_confident_target_leaders(
    target_candidates: dict[str, list[dict]],
    targets: tuple[QueryTarget, ...],
    limit: int,
) -> tuple[list[dict], str] | None:
    if limit <= 0 or not targets or len(targets) > limit:
        return None

    chosen: list[dict] = []
    for target in targets:
        candidates = target_candidates.get(target.slot, [])
        if not candidates:
            return None
        if not _score_has_clear_lead(candidates[0], candidates[1] if len(candidates) > 1 else None):
            return None
        chosen.append(dict(candidates[0]))

    return chosen[:limit], "top_score_lead"


def _rerank_with_llm(query: str, candidates: list[dict], limit: int) -> tuple[list[dict], bool]:
    if not candidates or not is_chat_provider_configured():
        return candidates[:limit], False
    if len(candidates) == 1:
        return candidates[:limit], False

    lines = []
    for idx, candidate in enumerate(candidates, start=1):
        slot = candidate.get("target_slot") or "target"
        lines.append(
            f'{idx}. [slot: {slot}] [function] {candidate["tag"]} '
            f'(label: {candidate["label"]}; heuristic: {candidate["reason"]})'
        )

    llm = create_chat_llm(temperature=0)
    response = llm.invoke(
        [
            SystemMessage(content=TAG_RERANK_PROMPT),
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
        key = candidate["tag"]
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
) -> dict:
    snapshot = await catalog_store.get_snapshot()
    pending, existing_count = await _load_expansion_work_from_db(
        limit=limit,
        force=force,
        tag_types=tag_types,
    )

    if limit is not None and limit <= 0:
        return {
            "status": "ok",
            "total_tags": len(snapshot.entries),
            "existing_items": existing_count,
            "source_of_truth": "database",
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
        if print_embedding_text:
            for item in generated.values():
                print(
                    f"[embedding_text] {item['tag_type']}:{item['tag']} -> {item['embedding_text']}",
                    flush=True,
                )
        generated_count += len(generated)

    return {
        "status": "ok",
        "total_tags": len(snapshot.entries),
        "existing_items": existing_count,
        "source_of_truth": "database",
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

        vectors = await asyncio.to_thread(encode_batch_or_none, texts)
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


async def search_tags(
    query: str,
    limit: int = 12,
    card_limit: int | None = 60,
    card_offset: int = 0,
) -> dict:
    started = time.perf_counter()
    query = query.strip()
    if not query:
        raise ValueError("Query must not be empty")

    logger.info(">>> AI Search query: %s", query)
    card_filters, card_filter_meta, analysis = await _card_filters_for_tag_query(query)
    tag_retrieval_query = str(card_filter_meta.get("tag_retrieval_query") or "").strip()

    if not tag_retrieval_query:
        card_result = await _cards_for_structured_filters(
            card_filters,
            card_limit=card_limit,
            card_offset=card_offset,
        )
        cards = card_result["cards"]
        total_cards = int(card_result["total"] or 0)
        catalog = {
            "total_tags": 0,
            "art_tags": 0,
            "function_tags": 0,
            "card_count": len(cards),
            "total_card_count": total_cards,
            "card_limit": card_limit,
            "card_offset": card_offset,
            **card_filter_meta,
            "searched_tags": 0,
            "etag": None,
            "loaded_at": None,
            "checked_at": None,
            "llm_used": bool(card_filter_meta.get("card_filter_plan_llm_used")),
            "type_hint": "function",
            "targets": [],
            "logic": None,
            "structured_only": True,
        }
        search_plan = {
            "mode": "structured_filters",
            "card_filters": card_filters,
            "suggested_queries": [],
            "catalog": catalog,
        }
        logger.info(
            "<<< AI Search final: %d/%d cards, offset=%d, structured_only=True, total took %.2fs",
            len(cards),
            total_cards,
            card_offset,
            time.perf_counter() - started,
        )
        return {
            "query": query,
            "suggested_queries": [],
            "matches": [],
            "cards": cards,
            "catalog": catalog,
            "search_plan": search_plan,
        }

    snapshot = await catalog_store.get_snapshot()
    targets = _build_search_targets(analysis)
    target_details = ", ".join(f"[{t.slot}] {t.intent}" for t in targets) if targets else "none"
    logic_dict = _logic_node_to_dict(analysis.logic, targets) if len(targets) > 1 else None
    if logic_dict:
        logger.info("<<< AI Search targets: %s | logic=%s", target_details, json.dumps(logic_dict, ensure_ascii=False))
    else:
        logger.info("<<< AI Search targets: %s", target_details)
    vector_started = time.perf_counter()
    vector_results_by_target = await _vector_search_entries_for_targets(targets)
    target_results: list[list[dict]] = []
    target_meta: list[dict] = []
    target_candidates: dict[str, list[dict]] = {}
    for target_index, target in enumerate(targets):
        vector_scored = (
            vector_results_by_target[target_index]
            if target_index < len(vector_results_by_target)
            else []
        )
        target_results.append(vector_scored)
        target_candidates[target.slot] = vector_scored
        target_meta.append(
            {
                "slot": target.slot,
                "intent": target.intent,
                "candidate_count": len(vector_scored),
            }
        )

    merged: dict[str, dict] = {}
    for result in target_results:
        for item in result:
            key = item["tag"]
            existing = merged.get(key)
            if existing is None or item["score"] > existing["score"]:
                merged[key] = item
    candidates = sorted(merged.values(), key=lambda item: -item["score"])
    logger.info(
        "<<< AI Search vector retrieval: %d total, %d unique, %.2fs",
        sum(len(result) for result in target_results),
        len(candidates),
        time.perf_counter() - vector_started,
    )
    rerank_query = analysis.intent or query
    if target_meta:
        target_summary = "; ".join(
            f'{item["slot"]}={item["intent"]}' for item in target_meta if item.get("intent")
        )
        if target_summary:
            rerank_query = f"{rerank_query}. Retrieval targets: {target_summary}"
    rerank_started = time.perf_counter()
    rerank_skip_reason = ""
    confident_selection = _select_confident_target_leaders(target_candidates, targets, limit)
    if confident_selection is not None:
        chosen, rerank_skip_reason = confident_selection
        llm_used = False
    else:
        chosen, llm_used = await asyncio.to_thread(_rerank_with_llm, rerank_query, candidates[:20], limit)
    chosen = _ensure_target_coverage(chosen, candidates, targets, limit)
    logger.info(
        "<<< AI Search rerank selected %d tags from %d candidates, llm_used=%s skip=%s in %.2fs",
        len(chosen),
        len(candidates),
        llm_used,
        rerank_skip_reason or "none",
        time.perf_counter() - rerank_started,
    )
    selected_parts = [
        "[%d] %s score=%.4f slot=%s"
        % (i, m.get("tag"), float(m.get("score") or 0.0), m.get("target_slot", "?"))
        for i, m in enumerate(chosen[:limit], start=1)
    ]
    logger.info("<<< AI Search selected %d tags: %s", len(chosen[:limit]), " | ".join(selected_parts))
    card_result = await _cards_for_tag_matches(
        chosen,
        logic=analysis.logic,
        card_filters=card_filters,
        card_limit=card_limit,
        card_offset=card_offset,
    )
    cards = card_result["cards"]
    total_cards = int(card_result["total"] or 0)
    logger.info(
        "<<< AI Search final: %d/%d cards, offset=%d, filters_used=%s, total took %.2fs",
        len(cards),
        total_cards,
        card_offset,
        card_filter_meta.get("card_filter_used"),
        time.perf_counter() - started,
    )

    total_tags = len(snapshot.entries)
    art_tags = sum(1 for entry in snapshot.entries if entry.tag_type == "art")
    function_tags = total_tags - art_tags
    suggested_queries = _compose_search_query(chosen, analysis.logic)
    catalog = {
        "total_tags": total_tags,
        "art_tags": art_tags,
        "function_tags": function_tags,
        "card_count": len(cards),
        "total_card_count": total_cards,
        "card_limit": card_limit,
        "card_offset": card_offset,
        **card_filter_meta,
        "searched_tags": sum(item["candidate_count"] for item in target_meta),
        "etag": snapshot.etag,
        "loaded_at": snapshot.loaded_at,
        "checked_at": snapshot.checked_at,
        "llm_used": llm_used,
        "type_hint": "function",
        "targets": target_meta,
        "logic": logic_dict,
        "rerank_skipped": bool(rerank_skip_reason),
        "rerank_skip_reason": rerank_skip_reason,
    }
    search_plan = {
        "chosen": chosen,
        "logic": logic_dict,
        "card_filters": card_filters,
        "suggested_queries": suggested_queries,
        "catalog": catalog,
        "tag_limit": limit,
    }

    return {
        "query": query,
        "suggested_queries": suggested_queries,
        "matches": chosen[:limit],
        "cards": cards,
        "catalog": catalog,
        "search_plan": search_plan,
    }
