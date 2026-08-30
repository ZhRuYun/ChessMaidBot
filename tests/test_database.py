import os
import shutil
import tempfile
from pathlib import Path
import unittest
from src.database.history_store import HistoryStore
from src.database.opening_book import OpeningBook
from src.database.unified_db import UnifiedDatabase


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_history_store_save_and_parse(self):
        store = HistoryStore(root=Path(self.test_dir))
        pgn = '[Event "Test"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0'
        summary = "Good opening development by White."
        filepath = store.save_game(pgn, result="1-0", llm_summary=summary)

        self.assertIsNotNone(filepath)
        self.assertTrue(os.path.exists(filepath))
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        parsed = store.parse_game_file(content)
        self.assertIn("1. e4 e5", parsed["pgn"])
        self.assertEqual(parsed["summary"], summary)

    def test_history_store_filter_criteria(self):
        store = HistoryStore(root=Path(self.test_dir))
        # 1. 0步无效棋局
        res1 = store.save_game('*', result="*")
        self.assertIsNone(res1)

        # 2. 未完赛棋局
        res2 = store.save_game('1. e4 e5 *', result="*")
        self.assertIsNone(res2)

        # 3. 正常认输/将死/求和结束的有效对局
        res3 = store.save_game('1. e4 e5 2. Nf3 Nc6 1-0', result="1-0", llm_summary="Resignation")
        self.assertIsNotNone(res3)
        self.assertEqual(len(store.list_games(filter_useless=True)), 1)

    def test_opening_book_query(self):
        ob = OpeningBook()
        self.assertTrue(hasattr(ob, "query_opening"))
        res = ob.query_opening("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
        self.assertTrue(res.get("in_book"))
        self.assertIn("King's Pawn Game", res.get("name", ""))

    def test_unified_database_query(self):
        udb = UnifiedDatabase(base_data_dir=self.test_dir)
        res = udb.query(category="opening", fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        self.assertIsNotNone(res)
        self.assertEqual(res.get("category"), "opening")
        self.assertIn("recommended_moves", res)


if __name__ == "__main__":
    unittest.main()
