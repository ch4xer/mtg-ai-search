import asyncio
import unittest
from unittest.mock import Mock, patch

from app.services import card_query_constraints, tag_reranker, tag_search_service


class AiSearchModelConfigurationTest(unittest.TestCase):
    @patch.object(card_query_constraints, "create_chat_llm")
    def test_search_plan_is_deterministic(self, create_llm):
        llm = create_llm.return_value
        llm.invoke.return_value = Mock(content="{}", usage_metadata={})

        result, _, _ = card_query_constraints.extract_card_search_constraints("能吸血的")

        self.assertEqual(result, {})
        system_prompt = llm.invoke.call_args.args[0][0].content
        self.assertIn("A structured filter describes a printed property of the cards", system_prompt)
        self.assertIn("Card types mentioned inside an effect or trigger condition", system_prompt)
        self.assertIn("每当施放瞬间或法术咒语时触发效果", system_prompt)
        create_llm.assert_called_once_with(temperature=0)

    @patch.object(tag_reranker, "is_chat_provider_configured", return_value=True)
    @patch.object(tag_reranker, "create_chat_llm")
    def test_reranker_receives_candidate_semantics(self, create_chat_llm, _configured):
        llm = create_chat_llm.return_value
        llm.invoke.return_value = Mock(
            content='{"selected":[{"id":1,"reason":"Matches damage-based life gain"}]}'
        )
        candidates = [
            {
                "tag": "gains-lifelink",
                "label": "gains lifelink",
                "score": 0.8,
                "reason": "Vector semantic match",
                "target_slot": "lifelink",
                "description": "A creature gains lifelink and its controller gains life from damage.",
                "aliases": ["damage-based life gain"],
                "retrieval_phrases": ["gain life equal to damage dealt"],
            },
            {
                "tag": "burn-self",
                "label": "burn self",
                "score": 0.75,
                "reason": "Vector semantic match",
                "target_slot": "lifelink",
                "description": "A creature deals damage to itself.",
                "aliases": ["self damage"],
                "retrieval_phrases": ["creature damages itself"],
            },
        ]

        selection = asyncio.run(
            tag_reranker.rerank_tags("Original user query: 能吸血的", candidates, 12)
        )

        prompt = llm.invoke.call_args.args[0][1].content
        system_prompt = llm.invoke.call_args.args[0][0].content
        self.assertTrue(selection.used_llm)
        self.assertEqual(selection.matches[0]["tag"], "gains-lifelink")
        self.assertIn("description: A creature gains lifelink", prompt)
        self.assertIn("aliases: damage-based life gain", prompt)
        self.assertIn("retrieval phrases: gain life equal to damage dealt", prompt)
        self.assertIn("description: A creature deals damage to itself", prompt)
        self.assertIn("Original user query", prompt)
        self.assertIn("semantic equality", system_prompt)
        self.assertIn("Never select both a broad category and a more precise tag", system_prompt)
        create_chat_llm.assert_called_once_with(temperature=0)

    @patch.object(tag_reranker, "is_chat_provider_configured", return_value=True)
    @patch.object(tag_reranker, "create_chat_llm")
    def test_reranker_can_abstain_without_falling_back_to_approximate_tags(self, create_chat_llm, _configured):
        create_chat_llm.return_value.invoke.return_value = Mock(content='{"selected":[]}')
        candidates = [
            {
                "tag": "cast-trigger-you",
                "label": "cast trigger you",
                "score": 0.8,
                "reason": "Vector semantic match",
                "target_slot": "cast_trigger",
                "description": "Triggers whenever its controller casts any spell.",
            },
            {
                "tag": "cast-trigger-other",
                "label": "cast trigger other",
                "score": 0.7,
                "reason": "Vector semantic match",
                "target_slot": "cast_trigger",
                "description": "Triggers whenever another player casts a spell.",
            },
        ]

        selection = asyncio.run(
            tag_reranker.rerank_tags(
                "Original user query: a narrowly qualified effect",
                candidates,
                12,
            )
        )

        self.assertTrue(selection.used_llm)
        self.assertEqual(selection.matches, [])

    @patch.object(tag_reranker, "is_chat_provider_configured", return_value=True)
    @patch.object(tag_reranker, "create_chat_llm")
    def test_reranker_uses_llm_even_for_a_single_candidate(self, create_chat_llm, _configured):
        create_chat_llm.return_value.invoke.return_value = Mock(
            content='{"selected":[{"id":1,"reason":"Exact semantic match"}]}'
        )
        candidates = [
            {
                "tag": "magecraft",
                "label": "magecraft",
                "score": 0.9,
                "reason": "Vector semantic match",
                "target_slot": "cast_trigger",
                "description": "Triggers when its controller casts or copies an instant or sorcery spell.",
            }
        ]

        selection = asyncio.run(
            tag_reranker.rerank_tags(
                "Original user query: 当施放瞬间或法术咒语时触发效果",
                candidates,
                12,
            )
        )

        self.assertTrue(selection.used_llm)
        self.assertEqual([candidate["tag"] for candidate in selection.matches], ["magecraft"])
        create_chat_llm.assert_called_once_with(temperature=0)
        create_chat_llm.return_value.invoke.assert_called_once()

    def test_rerank_context_keeps_original_query_and_normalized_targets(self):
        analysis = tag_search_service.QueryAnalysis(
            intent="Trigger when you cast an instant or sorcery spell.",
            expansions=(),
        )

        context = tag_search_service._rerank_search_context(
            "当施放瞬间或法术时触发效果",
            analysis,
            [{"slot": "magecraft", "intent": "Trigger when you cast an instant or sorcery spell."}],
        )

        self.assertIn("Original user query: 当施放瞬间或法术时触发效果", context)
        self.assertIn("Normalized overall intent: Trigger when you cast an instant or sorcery spell.", context)
        self.assertIn("Required target [magecraft]", context)


if __name__ == "__main__":
    unittest.main()
