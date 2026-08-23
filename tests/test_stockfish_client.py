"""
Stockfish 客户端 (模块4) 单元测试
"""
import unittest

from src.engine.stockfish_client import StockfishClient


class TestStockfishClient(unittest.TestCase):
    def setUp(self):
        self.client = StockfishClient()

    def tearDown(self):
        self.client.quit()

    def test_available_and_uci_handshake(self):
        if not self.client.available:
            self.skipTest("Stockfish 二进制未在 engines/ 目录下找到")

        self.client.start()
        self.assertIsNotNone(self.client._proc)

    def test_best_move(self):
        if not self.client.available:
            self.skipTest("Stockfish 二进制未在 engines/ 目录下找到")

        # 起始局面最佳走法之一
        move = self.client.best_move(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", movetime_ms=100
        )
        self.assertIsNotNone(move)
        self.assertIn(move, ["e2e4", "d2d4", "c2c4", "g1f3", "b1c3"])

    def test_skill_level_setting(self):
        self.client.set_skill_level(5)
        self.assertEqual(self.client.skill_level, 5)

    def test_analyse_multipv(self):
        if not self.client.available:
            self.skipTest("Stockfish 二进制未在 engines/ 目录下找到")

        results = self.client.analyse(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            depth=6,
            multipv=2,
        )
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("score_cp", results[0])
        self.assertIn("pv", results[0])


if __name__ == "__main__":
    unittest.main()
