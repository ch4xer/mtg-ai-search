import unittest

from app.repositories.sql.card_discovery_filters import build_discovery_filter


class CardDiscoveryFilterTest(unittest.TestCase):
    def test_cjk_query_searches_translation_fields(self):
        filter_spec = build_discovery_filter(q="闪电")

        self.assertIn("card_print_translations zt", filter_spec.where)
        self.assertIn("zt.name ILIKE $1", filter_spec.where)
        self.assertIn("zt.type_line ILIKE $1", filter_spec.where)
        self.assertIn("zt.oracle_text ILIKE $1", filter_spec.where)
        self.assertNotIn("zt.flavor_text ILIKE $1", filter_spec.where)
        self.assertIn("zt.set_name ILIKE $1", filter_spec.where)
        self.assertIn("jsonb_array_elements", filter_spec.where)
        self.assertIn("face.value ->> 'name' ILIKE $1", filter_spec.where)
        self.assertIn("face.value ->> 'type_line' ILIKE $1", filter_spec.where)
        self.assertIn("face.value ->> 'oracle_text' ILIKE $1", filter_spec.where)
        self.assertIn("face.value ->> 'set_name' ILIKE $1", filter_spec.where)
        self.assertNotIn("zt.card_faces::text", filter_spec.where)
        self.assertNotIn("face.value ->> 'flavor_text'", filter_spec.where)
        self.assertEqual(filter_spec.params, ["%闪电%"])

    def test_non_cjk_query_searches_english_card_fields(self):
        filter_spec = build_discovery_filter(q="lightning")

        self.assertIn("c.name ILIKE $1", filter_spec.where)
        self.assertIn("c.type_line ILIKE $1", filter_spec.where)
        self.assertIn("c.oracle_text ILIKE $1", filter_spec.where)
        self.assertNotIn("card_print_translations", filter_spec.where)
        self.assertEqual(filter_spec.params, ["%lightning%"])


if __name__ == "__main__":
    unittest.main()
