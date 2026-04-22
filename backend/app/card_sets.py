"""Classification helpers for non-standard Scryfall prints."""

from __future__ import annotations

from typing import Any

UNOFFICIAL_SET_CODES = frozenset({
    "ugl",   # Unglued
    "unh",   # Unhinged
    "ust",   # Unstable
    "und",   # Unsanctioned
    "unf",   # Unfinity / acorn-heavy funny set
    "cmb1",  # Mystery Booster Playtest Cards 2019
    "cmb2",  # Mystery Booster Playtest Cards 2021
    "mb2",   # Mystery Booster 2 future/playtest-style cards
    "past",  # Astral Cards
    "unk",   # Unknown Event
    "da1",   # Gavin's Unknown Event
})

PLAYTEST_SET_CODES = frozenset({
    "cmb1",
    "cmb2",
    "mb2",
    "past",
    "unk",
    "da1",
})

UNOFFICIAL_SET_NAME_MARKERS = (
    "playtest",
    "unknown event",
    "astral cards",
)

PLAYTEST_SET_NAME_MARKERS = (
    "playtest",
    "unknown event",
    "astral cards",
)


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def is_playtest_print(card: dict[str, Any]) -> bool:
    set_code = _lower(card.get("set"))
    set_name = _lower(card.get("set_name"))
    return set_code in PLAYTEST_SET_CODES or any(marker in set_name for marker in PLAYTEST_SET_NAME_MARKERS)


def is_unofficial_print(card: dict[str, Any]) -> bool:
    set_code = _lower(card.get("set"))
    set_name = _lower(card.get("set_name"))
    set_type = _lower(card.get("set_type"))
    security_stamp = _lower(card.get("security_stamp"))
    border_color = _lower(card.get("border_color"))

    return (
        set_type == "funny"
        or security_stamp == "acorn"
        or border_color == "silver"
        or set_code in UNOFFICIAL_SET_CODES
        or any(marker in set_name for marker in UNOFFICIAL_SET_NAME_MARKERS)
    )
