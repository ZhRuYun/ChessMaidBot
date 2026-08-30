import unittest
from pathlib import Path
from src.config import ENGINE_PATH
from src.engine.stockfish_client import StockfishClient
from scripts.download_assets import is_valid_stockfish_binary


class TestEngine(unittest.TestCase):
    def test_stockfish_client_creation_and_state(self):
        client = StockfishClient(binary_path=Path("non_existent_stockfish"))
        self.assertFalse(client.available)
        self.assertEqual(client.skill_level, 10)

    def test_real_engine_if_present(self):
        if is_valid_stockfish_binary(ENGINE_PATH):
            with StockfishClient(binary_path=ENGINE_PATH) as client:
                self.assertTrue(client.available)
                move = client.best_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", movetime_ms=100)
                self.assertIsNotNone(move)


if __name__ == "__main__":
    unittest.main()
