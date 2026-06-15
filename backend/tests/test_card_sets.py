import unittest

from app.card_sets import is_unofficial_print


class CardSetsTest(unittest.TestCase):
    def test_minigame_print_is_not_hidden_as_unofficial(self):
        self.assertFalse(is_unofficial_print({"set_type": "minigame"}))

    def test_funny_print_still_hidden_as_unofficial(self):
        self.assertTrue(is_unofficial_print({"set_type": "funny"}))

    def test_silver_border_print_still_hidden_as_unofficial(self):
        self.assertTrue(is_unofficial_print({"border_color": "silver"}))


if __name__ == "__main__":
    unittest.main()
