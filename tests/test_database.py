import os
import shutil
import tempfile
from pathlib import Path
import unittest
from src.database.history_store import HistoryStore
from src.database.opening_book import OpeningBook
from src.database.tactics_db import TacticsDatabase
from src.database.endgame_db import EndgameDatabase
from src.database.unified_db import UnifiedDatabase


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_history_store_save_and_parse(self):
        store = HistoryStore(root=Path(self.test_dir))
        pgn = '[Event "Test"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0'
        summary = "Good opening development by White."
        filepath = store.save_game(pgn, result="1-0", llm_summary=summary)

        self.assertTrue(os.path.exists(filepath))
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        parsed = store.parse_game_file(content)
        self.assertIn("1. e4 e5", parsed["pgn"])
        self.assertEqual(parsed["summary"], summary)

    def test_opening_and_tactics_and_endgame(self):
        ob = OpeningBook()
        self.assertTrue(hasattr(ob, "query_opening"))

        td = TacticsDatabase()
        self.assertTrue(hasattr(td, "query_tactics"))

        ed = EndgameDatabase()
        self.assertTrue(hasattr(ed, "query_endgame"))

    def test_unified_database_query(self):
        udb = UnifiedDatabase(base_data_dir=self.test_dir)
        res = udb.query(category="opening", fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        self.assertIsNotNone(res)
        self.assertEqual(res.get("category"), "opening")


if __name__ == "__main__":
    unittest.main()
