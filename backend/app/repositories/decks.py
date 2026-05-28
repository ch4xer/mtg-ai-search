"""Deck persistence boundary."""

from .sql.deck_analysis import get_deck_cards_for_analysis, update_deck_analysis
from .sql.deck_card_mutations import add_card_to_deck, remove_card_from_deck, update_deck_card_image
from .sql.deck_card_queries import get_deck_cards
from .sql.deck_core import create_deck, delete_deck, get_deck, get_user_decks, update_deck, update_deck_cover
from .sql.deck_exports import get_deck_card_images, get_deck_cards_for_export

__all__ = [
    "add_card_to_deck",
    "create_deck",
    "delete_deck",
    "get_deck",
    "get_deck_card_images",
    "get_deck_cards",
    "get_deck_cards_for_analysis",
    "get_deck_cards_for_export",
    "get_user_decks",
    "remove_card_from_deck",
    "update_deck",
    "update_deck_analysis",
    "update_deck_cover",
    "update_deck_card_image",
]
