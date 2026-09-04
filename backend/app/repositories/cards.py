"""Card persistence boundary."""

from .sql.card_discovery import discover_cards
from .sql.card_filter import filter_cards
from .sql.card_lookup import get_card_by_oracle_id, get_cards_by_names, get_cards_by_oracle_ids
from .sql.card_prints import get_card_print_by_set_cn, get_card_prints_by_oracle_id
from .sql.card_result_rows import get_cards_by_ids
from .sql.card_set_catalog import get_card_set_catalog
from .sql.card_special_queries import (
    get_card_function_tags,
    get_random_playable_card,
)
from .sql.card_text_search import text_match_cards
from .sql.card_vector_search import effect_vector_search_cards, search_abilities, vector_search_cards
from .sql.keyword_abilities import get_all_keywords, get_keyword_ability_rows

__all__ = [
    "discover_cards",
    "effect_vector_search_cards",
    "filter_cards",
    "get_all_keywords",
    "get_keyword_ability_rows",
    "get_card_by_oracle_id",
    "get_card_print_by_set_cn",
    "get_card_prints_by_oracle_id",
    "get_card_set_catalog",
    "get_card_function_tags",
    "get_cards_by_ids",
    "get_cards_by_names",
    "get_cards_by_oracle_ids",
    "get_random_playable_card",
    "search_abilities",
    "text_match_cards",
    "vector_search_cards",
]
