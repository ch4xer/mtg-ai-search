"""Shared MTG deck type helpers.

These helpers are the backend source of truth for deck-facing card
classification. Frontend code should consume the serialized fields instead of
parsing type lines.
"""

from __future__ import annotations

from typing import Any

DECK_TYPE_ORDER = (
    "Planeswalker",
    "Creature",
    "Sorcery",
    "Instant",
    "Artifact",
    "Enchantment",
    "Battle",
    "Land",
    "Other",
)

DECK_TYPE_SORT = {card_type: index for index, card_type in enumerate(DECK_TYPE_ORDER)}


def classify_deck_type(card: dict[str, Any]) -> str:
    type_line = card.get("type_line") or ""
    for card_type in DECK_TYPE_ORDER:
        if card_type != "Other" and card_type in type_line:
            return card_type
    return "Other"


def build_deck_rule_fields(card: dict[str, Any]) -> dict[str, Any]:
    deck_type = classify_deck_type(card)
    return {
        "deck_type": deck_type,
        "deck_type_sort": DECK_TYPE_SORT[deck_type],
    }


def deck_type_order_sql(type_line_expr: str = "c.type_line") -> str:
    cases = "\n".join(
        f"                    WHEN POSITION('{card_type}' IN COALESCE({type_line_expr}, '')) > 0 THEN {index}"
        for index, card_type in enumerate(DECK_TYPE_ORDER)
        if card_type != "Other"
    )
    return f"""CASE
{cases}
                    ELSE {DECK_TYPE_SORT["Other"]}
                  END"""
