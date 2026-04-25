"""Utilities for turning card text into searchable effect chunks."""

from __future__ import annotations

import json
import re
from typing import Any

_BULLET_RE = re.compile(r"(?=\n?[•−-]\s+)")
_WHITESPACE_RE = re.compile(r"\s+")
_TRIGGER_PREFIX_RE = re.compile(
    r"^(When(?:ever)?|At the beginning of|At the end of|If|As long as|Whenever one or more)\b",
    re.IGNORECASE,
)
_ABILITY_LABEL_RE = re.compile(r"^[^—]+ — (.+)$")
_TOP_LEVEL_SPLIT_RE = re.compile(r", then |; then |, and |; ", re.IGNORECASE)
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9{+\-\"“(])")


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _normalize_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _append_unique(chunks: list[str], seen: set[str], text: str) -> None:
    normalized = _normalize_text(text).strip(" ,;")
    if not normalized:
        return
    key = normalized.lower()
    if key in seen:
        return
    seen.add(key)
    chunks.append(normalized)


def _append_sentence_candidates(chunks: list[str], seen: set[str], text: str) -> None:
    _append_unique(chunks, seen, text)
    parts = _SENTENCE_BOUNDARY_RE.split(_normalize_text(text))
    if len(parts) <= 1:
        return
    for part in parts:
        _append_unique(chunks, seen, part)


def _split_clause_candidates(text: str) -> list[str]:
    text = _normalize_text(text)
    if not text:
        return []

    chunks: list[str] = []
    seen: set[str] = set()
    _append_sentence_candidates(chunks, seen, text)

    label_match = _ABILITY_LABEL_RE.match(text)
    if label_match:
        text = _normalize_text(label_match.group(1))
        _append_sentence_candidates(chunks, seen, text)

    if ": " in text:
        _, effect_text = text.split(": ", 1)
        _append_sentence_candidates(chunks, seen, effect_text)

    body = text
    if _TRIGGER_PREFIX_RE.match(text) and ", " in text:
        trigger, rest = text.split(", ", 1)
        _append_unique(chunks, seen, trigger)
        _append_sentence_candidates(chunks, seen, rest)
        body = rest

    if " where " in body.lower():
        where_index = body.lower().index(" where ")
        _append_sentence_candidates(chunks, seen, body[:where_index])

    if len(body) >= 60:
        for part in _TOP_LEVEL_SPLIT_RE.split(body):
            _append_sentence_candidates(chunks, seen, part)

    return chunks


def _split_text(text: str) -> list[str]:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    chunks: list[str] = []
    for paragraph in re.split(r"\n\s*\n|\n//\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if "•" in paragraph:
            mode_header = paragraph.split("•", 1)[0].strip()
            for part in _BULLET_RE.split(paragraph):
                part = part.strip()
                if not part:
                    continue
                if part.startswith("•") and mode_header:
                    chunks.extend(_split_clause_candidates(f"{mode_header} {part}"))
                else:
                    chunks.extend(_split_clause_candidates(part))
            continue

        for line in paragraph.split("\n"):
            line = _normalize_text(line)
            if line:
                chunks.extend(_split_clause_candidates(line))

    return chunks


def build_card_effect_chunks(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Return chunk rows for a card.

    Each row has face_index, chunk_index, effect_text, and source. Only chunks
    derived from actual oracle text are indexed for effect search.
    """
    chunks: list[dict[str, Any]] = []
    card_faces = _decode_json(card.get("card_faces")) or []

    if card_faces:
        for face_index, face in enumerate(card_faces):
            for text in _split_text(face.get("oracle_text") or ""):
                chunks.append({
                    "face_index": face_index,
                    "effect_text": text,
                    "source": "oracle_text",
                })
    else:
        for text in _split_text(card.get("oracle_text") or ""):
            chunks.append({
                "face_index": 0,
                "effect_text": text,
                "source": "oracle_text",
            })

    return [
        {**chunk, "chunk_index": index}
        for index, chunk in enumerate(chunks)
    ]
