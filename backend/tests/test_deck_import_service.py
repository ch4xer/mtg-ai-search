import unittest

from app.services.deck_import_service import parse_decklist


class ParseDecklistTest(unittest.TestCase):
    def test_cards_without_section_header_default_to_mainboard(self):
        entries = parse_decklist(
            """
            4 Island
            2 Opt
            """
        )

        self.assertEqual(
            entries,
            [(4, "Island", "mainboard", None, None), (2, "Opt", "mainboard", None, None)],
        )

    def test_deck_header_marks_following_cards_as_mainboard(self):
        entries = parse_decklist(
            """
            Sideboard
            1 Duress
            Deck
            4 Island
            """
        )

        self.assertEqual(
            entries,
            [(1, "Duress", "sideboard", None, None), (4, "Island", "mainboard", None, None)],
        )

    def test_arena_deck_and_sideboard_headers_are_not_imported_as_cards(self):
        entries = parse_decklist(
            """
            Deck
            4 Lightning Bolt

            Sideboard
            2 Pyroblast
            """
        )

        self.assertEqual(
            entries,
            [(4, "Lightning Bolt", "mainboard", None, None), (2, "Pyroblast", "sideboard", None, None)],
        )


if __name__ == "__main__":
    unittest.main()
