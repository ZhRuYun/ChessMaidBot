"""
历史棋局库 (模块6) 单元测试
"""
import tempfile
import unittest
from pathlib import Path

from src.database.history_store import HistoryStore


class TestHistoryStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = HistoryStore(root=Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_list(self):
        path = self.store.save_game('[Event "T"]\n\n1. e4 *\n', result="1-0")
        self.assertTrue(path.exists())
        self.assertIn("1-0", path.name)

        games = self.store.list_games()
        self.assertEqual(len(games), 1)
        self.assertIn("1. e4", HistoryStore.load_text(games[0]))

    def test_no_overwrite_on_same_second(self):
        first = self.store.save_game("game-a", result="1-0")
        second = self.store.save_game("game-b", result="1-0")
        self.assertNotEqual(first, second)
        self.assertEqual(len(self.store.list_games()), 2)

    def test_result_sanitized_for_filename(self):
        path = self.store.save_game("draw", result="1/2-1/2")
        self.assertEqual(path.name.count("/"), 0)


if __name__ == "__main__":
    unittest.main()
