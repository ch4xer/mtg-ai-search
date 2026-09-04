"""Shared ordering policy for card search result queries."""


def order_cards_by_mana_value(*tie_breakers: str, card_alias: str = "c") -> str:
    """Return stable SQL ordering with mana value as the primary key."""
    fields = [f"{card_alias}.cmc ASC NULLS LAST"]
    fields.extend(field for field in tie_breakers if field)
    return ", ".join(fields)
