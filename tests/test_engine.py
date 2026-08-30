import unittest
from pathlib import Path
from src.config import ENGINE_PATH
from src.engine.stockfish_client import StockfishClient, SharedEngine
from scripts.download_assets import is_valid_stockfish_binary


class TestEngine(unittest.TestCase):
    def test_stockfish_client_creation_and_state(self):
        client = StockfishClient(binary_path=Path("non_existent_stockfish"))
        self.assertFalse(client.available)
        self.assertEqual(client.skill_level, 10)

    def test_shared_engine_error_recovery(self):
        """共享引擎池: 引擎缺失时抛错并自动清理, 下次调用从干净状态重试"""
        pool = SharedEngine(binary_path=Path("non_existent_stockfish"))
        for _ in range(2):
            with self.assertRaises(Exception):
                pool.call(lambda client: client.best_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"))
        pool.reset()  # 幂等, 不应抛错

    def test_real_engine_if_present(self):
        if is_valid_stockfish_binary(ENGINE_PATH):
            with StockfishClient(binary_path=ENGINE_PATH) as client:
                self.assertTrue(client.available)
                move = client.best_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", movetime_ms=100)
                self.assertIsNotNone(move)


if __name__ == "__main__":
    unittest.main()
