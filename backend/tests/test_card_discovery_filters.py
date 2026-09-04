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
        self.assertEqual(filter_spec.params[:filter_spec.where_param_count], ["%lightning%"])

    def test_set_codes_are_normalized_and_use_a_print_join(self):
        filter_spec = build_discovery_filter(set_codes=[" LTR ", "ltc", "LTR"])

        self.assertIn("cp.set_code = ANY($1::text[])", filter_spec.where)
        self.assertEqual(filter_spec.params, [["ltc", "ltr"]])
        self.assertTrue(filter_spec.need_print_join)
        self.assertEqual(filter_spec.where_param_count, 1)

    def test_set_and_rarity_apply_to_the_same_print_alias(self):
        filter_spec = build_discovery_filter(rarities=["rare"], set_codes=["LTR"])

        self.assertIn("cp.rarity = ANY($1::text[])", filter_spec.where)
        self.assertIn("cp.set_code = ANY($2::text[])", filter_spec.where)
        self.assertEqual(filter_spec.params, [["rare"], ["ltr"]])
        self.assertTrue(filter_spec.need_print_join)

    def test_empty_set_codes_do_not_require_a_print_join(self):
        filter_spec = build_discovery_filter(set_codes=["", "  "])

        self.assertFalse(filter_spec.need_print_join)
        self.assertNotIn("cp.set_code", filter_spec.where)

    def test_selected_colors_require_the_exact_color_set(self):
        filter_spec = build_discovery_filter(colors=["R", "U"])

        self.assertIn("COALESCE(c.colors, ARRAY[]::text[]) @> $1::text[]", filter_spec.where)
        self.assertIn("COALESCE(c.colors, ARRAY[]::text[]) <@ $1::text[]", filter_spec.where)
        self.assertEqual(filter_spec.params, [["R", "U"]])

    def test_function_tags_match_tag_or_label_and_exclude_source_card(self):
        filter_spec = build_discovery_filter(
            function_tags=[" Cast-Trigger-You ", "Magecraft", "magecraft"],
            exclude_card_id="source-card",
        )

        self.assertIn("FROM card_tagger_tags ctt_filter", filter_spec.where)
        self.assertIn("LOWER(ctt_filter.tag) = ANY($1::text[])", filter_spec.where)
        self.assertIn("LOWER(tt_filter.label) = ANY($1::text[])", filter_spec.where)
        self.assertIn("c.id <> $2", filter_spec.where)
        self.assertEqual(filter_spec.params, [["cast-trigger-you", "magecraft"], "source-card"])


if __name__ == "__main__":
    unittest.main()
