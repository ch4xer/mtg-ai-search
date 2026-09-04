import unittest
from unittest.mock import AsyncMock, patch

from app.repositories.sql.card_search_order import order_cards_by_mana_value
from app.services import tag_search_service


class _RecordingSearchPool:
    def __init__(self):
        self.fetch_queries = []

    async def fetchval(self, query, *params):
        return 0

    async def fetch(self, query, *params):
        self.fetch_queries.append(query)
        return []


class CardSearchOrderTest(unittest.TestCase):
    def test_mana_value_is_primary_and_null_values_are_last(self):
        order = order_cards_by_mana_value(
            "matched_tag_count DESC",
            "ranked.name ASC",
            card_alias="ranked",
        )

        self.assertEqual(
            order,
            "ranked.cmc ASC NULLS LAST, matched_tag_count DESC, ranked.name ASC",
        )


class AiCardSearchOrderTest(unittest.IsolatedAsyncioTestCase):
    async def test_structured_results_are_ordered_by_mana_value(self):
        pool = _RecordingSearchPool()
        with patch.object(tag_search_service, "get_pool", AsyncMock(return_value=pool)):
            await tag_search_service._cards_for_structured_filters({"type": "Creature"})

        self.assertIn(
            "ORDER BY c.cmc ASC NULLS LAST, c.name ASC, c.id ASC",
            pool.fetch_queries[0],
        )

    async def test_tag_results_are_ordered_by_mana_value_before_relevance(self):
        pool = _RecordingSearchPool()
        with patch.object(tag_search_service, "get_pool", AsyncMock(return_value=pool)):
            await tag_search_service._cards_for_tag_matches(
                [{"tag": "draw", "score": 0.9}],
                card_limit=60,
            )

        self.assertIn(
            "ORDER BY aggregated.cmc ASC NULLS LAST, matched_tag_count DESC, "
            "tag_score_sum DESC, best_tag_rank ASC, aggregated.name ASC, aggregated.card_id ASC",
            pool.fetch_queries[0],
        )


if __name__ == "__main__":
    unittest.main()
