import unittest

from app.services import card_query_constraints
from app.services import tag_search_service


class ColorFilterSemanticsTest(unittest.TestCase):
    def test_all_colors_requires_every_symbol(self):
        params = []
        where = tag_search_service._build_structured_filter_where(
            {"colors": "R W"},
            params,
            card_alias="c",
        )

        self.assertIn("COALESCE(c.colors, ARRAY[]::text[]) @> $1::text[]", where)
        self.assertNotIn("cardinality", where)
        self.assertEqual(params, [["R", "W"]])

    def test_any_colors_matches_either_symbol(self):
        params = []
        where = tag_search_service._build_structured_filter_where(
            {"colors": "any:R W"},
            params,
            card_alias="c",
        )

        self.assertIn("COALESCE(c.colors, ARRAY[]::text[]) && $1::text[]", where)
        self.assertNotIn("cardinality", where)
        self.assertEqual(params, [["R", "W"]])

    def test_exact_colors_requires_only_those_symbols(self):
        params = []
        where = tag_search_service._build_structured_filter_where(
            {"colors": "=R W"},
            params,
            card_alias="c",
        )

        self.assertIn("COALESCE(c.colors, ARRAY[]::text[]) @> $1::text[]", where)
        self.assertIn("cardinality(COALESCE(c.colors, ARRAY[]::text[])) = $2", where)
        self.assertEqual(params, [["R", "W"], 2])

    def test_excluded_colors_reject_any_symbol(self):
        params = []
        where = tag_search_service._build_structured_filter_where(
            {"excluded_colors": "R W"},
            params,
            card_alias="c",
        )

        self.assertIn("NOT (COALESCE(c.colors, ARRAY[]::text[]) && $1::text[])", where)
        self.assertEqual(params, [["R", "W"]])

class AiSearchPlanTest(unittest.TestCase):
    def test_parser_omits_empty_plan_fields(self):
        parsed = card_query_constraints._parse_optimizer_response(
            """
            {
              "type": "Creature",
              "colors": "any:R W",
              "excluded_colors": "B",
              "released_at": "",
              "layout": "",
              "cmc": "",
              "power": "",
              "toughness": "",
              "targets": [],
              "logic": null
            }
            """
        )

        self.assertEqual(parsed, {"type": "Creature", "colors": "any:R W", "excluded_colors": "B"})

    def test_empty_target_plan_has_no_tag_targets(self):
        analysis = tag_search_service._analysis_from_search_plan(
            "Black Lotus",
            {},
            "",
        )

        self.assertEqual(analysis.targets, ())
        self.assertIsNone(analysis.logic)
        self.assertEqual(analysis.intent, "")

    def test_retrieval_query_comes_from_targets(self):
        plan = {
            "targets": [
                {
                    "slot": "opponent_discard",
                    "intent": "Target opponent discards a card.",
                },
                {
                    "slot": "opponent_life_loss",
                    "intent": "Opponent loses life.",
                },
            ],
        }

        query = tag_search_service._tag_retrieval_query_from_plan(plan)

        self.assertEqual(query, "Target opponent discards a card. Opponent loses life")

    def test_plan_parses_multiple_and_targets(self):
        target_one = {
            "slot": "opponent_discard",
            "intent": "Target opponent discards a card.",
        }
        target_two = {
            "slot": "opponent_life_loss",
            "intent": "Opponent loses life.",
        }
        analysis = tag_search_service._analysis_from_search_plan(
            "discard and lose life",
            {
                "targets": [target_one, target_two],
                "logic": {
                    "op": "and",
                    "children": ["opponent_discard", "opponent_life_loss"],
                },
            },
            "target opponent discards a card and loses life",
        )

        self.assertEqual(len(analysis.targets), 2)
        self.assertEqual(analysis.logic.op, "and")
        self.assertEqual([target.slot for target in analysis.targets], ["opponent_discard", "opponent_life_loss"])

    def test_logic_dict_uses_slot_string_leaves(self):
        target_one = tag_search_service.QueryTarget(
            intent="Target opponent discards a card.",
            expansions=("Target opponent discards a card.",),
            slot="opponent_discard",
        )
        target_two = tag_search_service.QueryTarget(
            intent="Opponent loses life.",
            expansions=("Opponent loses life.",),
            slot="opponent_life_loss",
        )
        logic = tag_search_service.QueryLogicNode(
            op="and",
            children=(
                tag_search_service.QueryLogicNode(op="target", slot="opponent_discard", target_index=0),
                tag_search_service.QueryLogicNode(op="target", slot="opponent_life_loss", target_index=1),
            ),
        )

        logic_dict = tag_search_service._logic_node_to_dict(logic, (target_one, target_two))

        self.assertEqual(logic_dict, {"op": "and", "children": ["opponent_discard", "opponent_life_loss"]})

    def test_rerank_skip_when_top_score_clearly_leads(self):
        target = tag_search_service.QueryTarget(
            intent="Target opponent discards a card.",
            expansions=("discard a card",),
            slot="opponent_discard",
        )
        selected = tag_search_service._select_confident_target_leaders(
            {
                "opponent_discard": [
                    {"tag_type": "function", "tag": "discard", "score": 0.032, "target_slot": "opponent_discard"},
                    {"tag_type": "function", "tag": "loot", "score": 0.016, "target_slot": "opponent_discard"},
                ]
            },
            (target,),
            12,
        )

        self.assertIsNotNone(selected)
        chosen, reason = selected
        self.assertEqual(reason, "top_score_lead")
        self.assertEqual(chosen[0]["tag"], "discard")

    def test_rerank_not_skipped_when_top_scores_are_close(self):
        target = tag_search_service.QueryTarget(
            intent="Target opponent discards a card.",
            expansions=("discard a card",),
            slot="opponent_discard",
        )

        selected = tag_search_service._select_confident_target_leaders(
            {
                "opponent_discard": [
                    {"tag_type": "function", "tag": "discard", "score": 0.032, "target_slot": "opponent_discard"},
                    {"tag_type": "function", "tag": "opponent-discards", "score": 0.030, "target_slot": "opponent_discard"},
                ]
            },
            (target,),
            12,
        )

        self.assertIsNone(selected)


if __name__ == "__main__":
    unittest.main()
