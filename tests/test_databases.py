"""
开局库、EPD 战术编码库与残局库模块的单元测试
"""
import unittest
import tempfile
import shutil
from pathlib import Path
import chess

from src.database.opening_book import OpeningBook, OpeningMoveEntry
from src.database.tactics_db import TacticsDatabase, TacticPuzzle
from src.database.endgame_db import EndgameDatabase, EndgameEvaluation
from src.database.history_store import HistoryStore


class TestOpeningBook(unittest.TestCase):
    def setUp(self):
        self.opening_book = OpeningBook(book_path=Path("/non_existent/path.bin"))

    def test_builtin_starting_position(self):
        board = chess.Board()
        query = self.opening_book.query_opening(board)
        self.assertTrue(query["in_book"])
        self.assertEqual(query["eco"], "A00")
        moves = [m["san"] for m in query["recommended_moves"]]
        self.assertIn("e4", moves)
        self.assertIn("d4", moves)

    def test_builtin_sicilian_variation(self):
        board = chess.Board()
        board.push_san("e4")
        board.push_san("c5")
        query = self.opening_book.query_opening(board)
        self.assertTrue(query["in_book"])
        self.assertEqual(query["eco"], "B20")
        self.assertIn("Sicilian", query["name"])
        moves = [m["san"] for m in query["recommended_moves"]]
        self.assertIn("Nf3", moves)

    def test_unknown_position(self):
        board = chess.Board("8/8/8/8/8/8/8/4K2k w - - 0 1")
        query = self.opening_book.query_opening(board)
        self.assertFalse(query["in_book"])
        self.assertEqual(query["eco"], "A00")
        self.assertEqual(len(query["recommended_moves"]), 0)


class TestTacticsDatabase(unittest.TestCase):
    def setUp(self):
        self.tactics_db = TacticsDatabase(epd_path=Path("/non_existent/tactics.epd"))

    def test_builtin_tactics_loaded(self):
        query = self.tactics_db.query_tactics(limit=10)
        self.assertGreater(query["total_available"], 0)
        self.assertGreater(len(query["puzzles"]), 0)

    def test_parse_epd_line(self):
        epd_line = '6k1/5ppp/8/8/8/8/1Q4PP/6K1 w - - 0 1 bm Qb8#; id "backrank_test"; c0 "底线杀棋";'
        puzzle = self.tactics_db.parse_epd_line(epd_line)
        self.assertIsNotNone(puzzle)
        self.assertEqual(puzzle.id, "backrank_test")
        self.assertIn("Qb8#", puzzle.bm)
        self.assertEqual(puzzle.theme, "checkmate")

    def test_find_tactics_for_position(self):
        fen = "6k1/5ppp/8/8/8/8/1Q4PP/6K1 w - - 0 1"
        puzzle = self.tactics_db.find_tactics_for_position(fen)
        self.assertIsNotNone(puzzle)
        self.assertEqual(puzzle.theme, "checkmate")

    def test_theme_filtering(self):
        query = self.tactics_db.query_tactics(theme="checkmate", limit=5)
        for p in query["puzzles"]:
            self.assertEqual(p["theme"], "checkmate")


class TestEndgameDatabase(unittest.TestCase):
    def setUp(self):
        self.endgame_db = EndgameDatabase(syzygy_path=Path("/non_existent/syzygy"))

    def tearDown(self):
        self.endgame_db.close()

    def test_insufficient_material(self):
        # 王对王和单象
        board = chess.Board("8/8/8/8/8/5K2/8/4k1b1 w - - 0 1")
        eval_res = self.endgame_db.evaluate(board)
        self.assertTrue(eval_res.is_theoretical_endgame)
        self.assertEqual(eval_res.wdl, 0)
        self.assertIn("Draw", eval_res.wdl_label)

    def test_queen_vs_bare_king(self):
        # 白方王后对单黑王
        board = chess.Board("8/8/8/8/8/5K2/8/4k1Q1 w - - 0 1")
        eval_res = self.endgame_db.evaluate(board)
        self.assertTrue(eval_res.is_theoretical_endgame)
        self.assertEqual(eval_res.wdl, 2)
        self.assertIn("必胜", eval_res.wdl_label)
        self.assertIn("单后杀单王", eval_res.advice)

    def test_rook_vs_bare_king(self):
        # 白方单车对单黑王
        board = chess.Board("8/8/8/8/8/5K2/8/4k1R1 w - - 0 1")
        eval_res = self.endgame_db.evaluate(board)
        self.assertTrue(eval_res.is_theoretical_endgame)
        self.assertEqual(eval_res.wdl, 2)
        self.assertIn("必胜", eval_res.wdl_label)
        self.assertIn("单车杀单王", eval_res.advice)

    def test_query_endgame(self):
        res = self.endgame_db.query_endgame("8/8/8/8/8/5K2/8/4k1Q1 w - - 0 1")
        self.assertEqual(res["category"], "endgame")
        self.assertTrue(res["is_endgame"])
        self.assertIn("单后", res["maid_advice"])


class TestDatabaseIntegrationInHistoryStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.history_store = HistoryStore(root=Path(self.temp_dir))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_query_opening_via_history_store(self):
        res = self.history_store.query_database("opening", fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
        self.assertEqual(res["category"], "opening")
        self.assertEqual(res["eco"], "B00")
        self.assertTrue(res["in_book"])

    def test_query_tactics_via_history_store(self):
        fen = "6k1/5ppp/8/8/8/8/1Q4PP/6K1 w - - 0 1"
        res = self.history_store.query_database("tactics", fen=fen)
        self.assertEqual(res["category"], "tactics")
        self.assertEqual(res["status"], "matched")
        self.assertIn("Qb8#", res["puzzle"]["best_moves"])

    def test_query_endgame_via_history_store(self):
        fen = "8/8/8/8/8/5K2/8/4k1Q1 w - - 0 1"
        res = self.history_store.query_database("endgame", fen=fen)
        self.assertEqual(res["category"], "endgame")
        self.assertEqual(res["wdl"], 2)


if __name__ == "__main__":
    unittest.main()
