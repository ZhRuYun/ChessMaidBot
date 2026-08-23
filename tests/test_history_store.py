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

    def test_save_and_parse_with_llm_summary(self):
        path = self.store.save_game(
            '[Event "Test"]\n\n1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0\n',
            result="1-0",
            llm_summary="白方使用了学者将死（Scholar's Mate），黑方防守疏忽。",
        )
        self.assertTrue(path.exists())
        content = HistoryStore.load_text(path)
        self.assertIn("LLM GAME SUMMARY", content)
        self.assertIn("学者将死", content)

        parsed = HistoryStore.parse_game_file(content)
        self.assertIn("Qxf7#", parsed["pgn"])
        self.assertIn("学者将死", parsed["summary"])

    def test_no_overwrite_on_same_second(self):
        first = self.store.save_game('[Event "A"]\n\n1. e4 e5 1-0\n', result="1-0")
        second = self.store.save_game('[Event "B"]\n\n1. d4 d5 1-0\n', result="1-0")
        self.assertNotEqual(first, second)
        self.assertEqual(len(self.store.list_games()), 2)

    def test_filter_useless_games(self):
        # 0 步认输或求和
        empty_resign = '[Event "Casual"]\n[Result "0-1"]\n\n0-1\n'
        empty_draw = '[Event "Casual"]\n[Result "1/2-1/2"]\n\n1/2-1/2\n'
        valid_game = '[Event "Casual"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 1-0\n'

        self.store.save_game(empty_resign, result="0-1")
        self.store.save_game(empty_draw, result="1/2-1/2")
        self.store.save_game(valid_game, result="1-0")

        # 默认过滤
        useful_games = self.store.list_games(filter_useless=True)
        self.assertEqual(len(useful_games), 1)

        # 不加过滤列出全部
        all_games = self.store.list_games(filter_useless=False)
        self.assertEqual(len(all_games), 3)

    def test_query_database_history_and_categories(self):
        self.store.save_game('[Event "T1"]\n\n1. e4 e5 *\n', result="*")
        res_history = self.store.query_database("history", limit=2)
        self.assertEqual(res_history["category"], "history")
        self.assertGreaterEqual(res_history["count"], 1)
        self.assertEqual(len(res_history["games"]), 1)

        res_opening = self.store.query_database("opening")
        self.assertEqual(res_opening["status"], "ready")

        res_invalid = self.store.query_database("non_existent")
        self.assertIn("error", res_invalid)


if __name__ == "__main__":
    unittest.main()
