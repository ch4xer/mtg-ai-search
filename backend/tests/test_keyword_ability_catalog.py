import unittest
from unittest.mock import AsyncMock, patch

from app.keyword_ability_catalog import concise_rules_fallback, core_keyword_explanation
from app.services.search_service import list_keyword_abilities


class KeywordAbilityCatalogTest(unittest.TestCase):
    def test_rules_fallback_skips_generic_ability_classification(self):
        description = (
            "Annihilator is a triggered ability. "
            "“Annihilator N” means “Whenever this creature attacks, defending player sacrifices N permanents.” "
            "Multiple instances trigger separately."
        )

        self.assertEqual(
            concise_rules_fallback(description),
            "“Annihilator N” means “Whenever this creature attacks, defending player sacrifices N permanents.”",
        )

    def test_core_explanations_are_bilingual(self):
        flying = core_keyword_explanation("FLYING")

        self.assertEqual(flying["name_zh"], "飞行")
        self.assertIn("flying or reach", flying["description_en"])
        self.assertIn("飞行或延势", flying["description_zh"])


class KeywordAbilityCatalogServiceTest(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.search_service.get_keyword_ability_rows", new_callable=AsyncMock)
    async def test_catalog_uses_core_translation_and_keeps_stored_entries(self, get_rows):
        get_rows.return_value = [
            {"name": "Flying", "name_zh": "", "description": "", "description_zh": ""},
            {
                "name": "Custom ability",
                "name_zh": "自定义异能",
                "description": "Do the custom thing.",
                "description_zh": "执行自定义动作。",
            },
        ]

        result = await list_keyword_abilities()
        abilities = {ability["name"].lower(): ability for ability in result["abilities"]}

        self.assertEqual(abilities["flying"]["name_zh"], "飞行")
        self.assertEqual(abilities["custom ability"]["description_zh"], "执行自定义动作。")


if __name__ == "__main__":
    unittest.main()
