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
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", movetime_ms=200
        )
        self.assertIsNotNone(move)
        self.assertIn(move, ["e2e4", "d2d4", "c2c4", "g1f3", "b1c3", "e2e3"])

    def test_skill_level_setting(self):
        self.client.set_skill_level(5)
        self.assertEqual(self.client.skill_level, 5)
        self.assertIsNone(self.client.target_elo)

    def test_target_elo_setting(self):
        self.client.set_elo(1800)
        self.assertEqual(self.client.target_elo, 1800)
        self.client.set_elo(4000)
        self.assertEqual(self.client.target_elo, 3190)
        self.client.set_elo(400)
        self.assertEqual(self.client.target_elo, 500)

    def test_get_state_api(self):
        if not self.client.available:
            self.skipTest("Stockfish 二进制未在 engines/ 目录下找到")

        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        res_move = self.client.get_state(fen, state_type="best_move", movetime_ms=100)
        self.assertTrue(res_move.get("available"))
        self.assertIsNotNone(res_move.get("best_move"))

        res_eval = self.client.get_state(fen, state_type="analyse", depth=5, multipv=1)
        self.assertTrue(res_eval.get("available"))
        self.assertIsInstance(res_eval.get("analysis"), list)


if __name__ == "__main__":
    unittest.main()
