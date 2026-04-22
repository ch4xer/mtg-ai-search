"""Utilities for turning card text into searchable effect chunks."""

from __future__ import annotations

import json
import re
from typing import Any

_BULLET_RE = re.compile(r"(?=\n?[•−-]\s+)")
_WHITESPACE_RE = re.compile(r"\s+")


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _normalize_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


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
                    chunks.append(_normalize_text(f"{mode_header} {part}"))
                else:
                    chunks.append(_normalize_text(part))
            continue

        for line in paragraph.split("\n"):
            line = _normalize_text(line)
            if line:
                chunks.append(line)

    return chunks


def build_card_effect_chunks(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Return chunk rows for a card.

    Each row has face_index, chunk_index, effect_text, and source. Keywords are
    included as short chunks so keyword-only abilities like lifelink can match
    effect searches even when oracle text is sparse.
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

    existing = {chunk["effect_text"].lower() for chunk in chunks}
    for keyword in card.get("keywords") or []:
        keyword_text = _normalize_text(str(keyword))
        if keyword_text and keyword_text.lower() not in existing:
            chunks.append({
                "face_index": 0,
                "effect_text": keyword_text,
                "source": "keyword",
            })
            existing.add(keyword_text.lower())

    return [
        {**chunk, "chunk_index": index}
        for index, chunk in enumerate(chunks)
    ]
