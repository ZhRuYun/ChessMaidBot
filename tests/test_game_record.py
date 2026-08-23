"""
走法历史记录管理 (双栏记谱) 单元测试
"""
import unittest

from src.core.game_record import MoveHistoryManager


class TestMoveHistoryManager(unittest.TestCase):
    def setUp(self):
        self.history = MoveHistoryManager()

    def test_white_black_pairing(self):
        self.history.add_move("e4", True, "fen1")
        self.history.add_move("e5", False, "fen2")
        self.assertEqual(len(self.history.records), 1)

        record = self.history.records[0]
        self.assertEqual(record.white_san, "e4")
        self.assertEqual(record.black_san, "e5")
        self.assertEqual(record.fen_after_white, "fen1")
        self.assertEqual(record.fen_after_black, "fen2")

        self.history.add_move("Nf3", True, "fen3")
        self.assertEqual(len(self.history.records), 2)
        self.assertEqual(self.history.records[1].move_number, 2)

    def test_pop_black_move_keeps_row(self):
        self.history.add_move("e4", True, "fen1")
        self.history.add_move("e5", False, "fen2")

        removed_row, idx = self.history.pop_move()
        self.assertFalse(removed_row)
        self.assertEqual(idx, 0)
        self.assertEqual(self.history.records[0].white_san, "e4")
        self.assertEqual(self.history.records[0].black_san, "")

    def test_pop_white_move_removes_row(self):
        self.history.add_move("e4", True, "fen1")
        removed_row, idx = self.history.pop_move()
        self.assertTrue(removed_row)
        self.assertEqual(len(self.history.records), 0)

    def test_black_first_position_uses_placeholder(self):
        self.history.add_move("e5", False, "fen1")
        record = self.history.records[0]
        self.assertEqual(record.white_san, "...")
        self.assertEqual(record.black_san, "e5")

        # 占位行只有黑方着法, 悔棋应整行删除
        removed_row, _ = self.history.pop_move()
        self.assertTrue(removed_row)
        self.assertEqual(len(self.history.records), 0)

    def test_black_first_full_round_then_undo(self):
        self.history.add_move("e5", False, "fen1")
        self.history.add_move("e4", True, "fen2")
        self.history.add_move("Nf6", False, "fen3")
        self.assertEqual(len(self.history.records), 2)

        removed_row, _ = self.history.pop_move()
        self.assertFalse(removed_row)
        removed_row, _ = self.history.pop_move()
        self.assertTrue(removed_row)
        # 只剩黑先的占位行
        self.assertEqual(len(self.history.records), 1)
        self.assertEqual(self.history.last_san(), "e5")

    def test_last_san(self):
        self.assertIsNone(self.history.last_san())
        self.history.add_move("e4", True, "fen1")
        self.assertEqual(self.history.last_san(), "e4")
        self.history.add_move("e5", False, "fen2")
        self.assertEqual(self.history.last_san(), "e5")

    def test_clear(self):
        self.history.add_move("e4", True, "fen1")
        self.history.clear()
        self.assertEqual(self.history.records, [])
        self.assertEqual(self.history.move_count, 0)


if __name__ == "__main__":
    unittest.main()
