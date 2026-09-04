import unittest
from unittest.mock import AsyncMock, patch

from app.repositories.sql import card_special_queries


class _RandomPool:
    def __init__(self, values):
        self.values = list(values)
        self.queries = []

    async def fetchval(self, query, *params):
        self.queries.append((query, params))
        return self.values.pop(0)


class CardSpecialQueriesTest(unittest.IsolatedAsyncioTestCase):
    async def test_random_card_excludes_unofficial_playtest_and_current_card(self):
        pool = _RandomPool(["next-id"])
        with (
            patch.object(card_special_queries, "get_pool", AsyncMock(return_value=pool)),
            patch.object(
                card_special_queries,
                "get_cards_by_ids",
                AsyncMock(return_value=[{"id": "next-id", "name": "Next"}]),
            ) as get_cards,
        ):
            card = await card_special_queries.get_random_playable_card("current-id")

        self.assertEqual(card["id"], "next-id")
        self.assertIn("NOT COALESCE(is_unofficial, FALSE)", pool.queries[0][0])
        self.assertIn("NOT COALESCE(is_playtest, FALSE)", pool.queries[0][0])
        self.assertEqual(pool.queries[0][1], ("current-id",))
        get_cards.assert_awaited_once_with(["next-id"])

    async def test_random_card_falls_back_when_only_excluded_card_exists(self):
        pool = _RandomPool([None, "only-id"])
        with (
            patch.object(card_special_queries, "get_pool", AsyncMock(return_value=pool)),
            patch.object(
                card_special_queries,
                "get_cards_by_ids",
                AsyncMock(return_value=[{"id": "only-id"}]),
            ),
        ):
            card = await card_special_queries.get_random_playable_card("only-id")

        self.assertEqual(card["id"], "only-id")
        self.assertEqual(len(pool.queries), 2)

if __name__ == "__main__":
    unittest.main()
