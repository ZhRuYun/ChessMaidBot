import unittest
import chess
from src.core.board_state import BoardState
from src.core.game_record import MoveHistoryManager


class TestCore(unittest.TestCase):
    def test_board_state_moves_and_undo(self):
        state = BoardState()
        self.assertEqual(state.turn, chess.WHITE)
        move = chess.Move.from_uci("e2e4")
        self.assertTrue(state.is_legal(move))

        ok, san, captured = state.make_move(move)
        self.assertTrue(ok)
        self.assertEqual(san, "e4")
        self.assertIsNone(captured)
        self.assertEqual(state.turn, chess.BLACK)
        self.assertEqual(len(state.move_stack_san), 1)

        popped = state.undo_move()
        self.assertEqual(popped, move)
        self.assertEqual(state.turn, chess.WHITE)
        self.assertEqual(len(state.move_stack_san), 0)

    def test_board_state_pgn_export_import(self):
        state = BoardState()
        state.make_move(chess.Move.from_uci("e2e4"))
        state.make_move(chess.Move.from_uci("e7e5"))
        pgn_text = state.export_pgn()
        self.assertIn("1. e4 e5", pgn_text)

        new_state = BoardState()
        success = new_state.import_pgn(pgn_text)
        self.assertTrue(success)
        self.assertEqual(len(new_state.move_stack_san), 2)
        self.assertEqual(new_state.get_fen(), state.get_fen())

    def test_move_history_manager(self):
        mgr = MoveHistoryManager()
        mgr.add_move("e4", is_white=True, fen="fen1")
        self.assertEqual(mgr.move_count, 1)
        rec = mgr.records[0]
        self.assertEqual(rec.white_san, "e4")
        self.assertEqual(rec.black_san, "")

        mgr.add_move("e5", is_white=False, fen="fen2")
        self.assertEqual(mgr.move_count, 1)
        rec = mgr.records[0]
        self.assertEqual(rec.black_san, "e5")

        mgr.pop_move()
        self.assertEqual(mgr.records[0].black_san, "")
        mgr.pop_move()
        self.assertEqual(mgr.move_count, 0)


if __name__ == "__main__":
    unittest.main()
