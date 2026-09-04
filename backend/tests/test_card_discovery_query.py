import unittest

from app.repositories.sql.card_discovery import _fetch_discovery_page
from app.repositories.sql.card_discovery_filters import build_discovery_filter


class _RecordingPool:
    def __init__(self):
        self.query = ""
        self.params = ()

    async def fetch(self, query, *params):
        self.query = query
        self.params = params
        return []


class CardDiscoveryQueryTest(unittest.IsolatedAsyncioTestCase):
    async def test_set_filter_selects_and_displays_the_same_print(self):
        pool = _RecordingPool()
        filter_spec = build_discovery_filter(set_codes=["ltr"])

        await _fetch_discovery_page(pool, filter_spec, page=1, page_size=60)

        self.assertIn("cp.id AS matched_print_id", pool.query)
        self.assertIn("JOIN card_prints dp ON dp.id = sub.matched_print_id", pool.query)
        self.assertIn("zt.print_id = dp.id", pool.query)
        self.assertNotIn("ORDER BY 0", pool.query)
        self.assertIn("ORDER BY c.cmc ASC NULLS LAST, c.name ASC, c.id ASC", pool.query)
        self.assertEqual(pool.params, (["ltr"], 60, 0))


if __name__ == "__main__":
    unittest.main()
