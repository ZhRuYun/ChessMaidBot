"""
核心规则与王车易位 (含 Lichess 交互) 单元测试
"""
import unittest
import chess
from src.core.board_state import BoardState, GameResult

class TestBoardState(unittest.TestCase):
    def setUp(self):
        self.state = BoardState()

    def test_initial_state(self):
        self.assertEqual(self.state.turn, chess.WHITE)
        self.assertEqual(self.state.get_fen(), chess.STARTING_FEN)
        self.assertFalse(self.state.is_game_over())
        self.assertIsNone(self.state.last_move)

    def test_legal_moves(self):
        move = chess.Move.from_uci("e2e4")
        self.assertTrue(self.state.is_legal(move))

        illegal_move = chess.Move.from_uci("e2e5")
        self.assertFalse(self.state.is_legal(illegal_move))

    def test_lichess_style_castling_kingside(self):
        self.state.reset("r1bqk2r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        m_std = self.state.resolve_castling_or_normal_move(chess.E1, chess.G1)
        self.assertIsNotNone(m_std)
        self.assertEqual(m_std.uci(), "e1g1")

        m_lichess = self.state.resolve_castling_or_normal_move(chess.E1, chess.H1)
        self.assertIsNotNone(m_lichess)
        self.assertEqual(m_lichess.uci(), "e1g1")

    def test_lichess_style_castling_queenside(self):
        self.state.reset("r3k2r/pppq1ppp/2npbn2/4p3/4P3/2NPBN2/PPPQ1PPP/R3K2R w KQkq - 6 8")
        m_lichess = self.state.resolve_castling_or_normal_move(chess.E1, chess.A1)
        self.assertIsNotNone(m_lichess)
        self.assertEqual(m_lichess.uci(), "e1c1")

    def test_scholar_mate_checkmate(self):
        moves = ["e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"]
        for m in moves:
            success, _, _ = self.state.make_uci_move(m)
            self.assertTrue(success)

        status = self.state.get_game_status()
        self.assertTrue(status["is_over"])
        self.assertTrue(status["is_checkmate"])
        self.assertEqual(status["result"], GameResult.WHITE_WINS)

    def test_pgn_and_fen_export(self):
        self.state.make_uci_move("e2e4")
        self.state.make_uci_move("e7e5")
        pgn_text = self.state.export_pgn()
        self.assertIn("1. e4 e5", pgn_text)

        fen_text = self.state.get_fen()
        self.assertIn("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", fen_text)

    def test_undo_restores_captured_pieces(self):
        for uci in ["e2e4", "d7d5", "e4d5"]:
            self.assertTrue(self.state.make_uci_move(uci)[0])
        self.assertEqual(self.state.captured_pieces["black"], ["p"])

        self.state.undo_move()
        self.assertEqual(self.state.captured_pieces["black"], [])
        self.assertEqual(self.state.move_stack_san, ["e4", "d5"])

    def test_undo_restores_en_passant_capture(self):
        for uci in ["e2e4", "a7a6", "e4e5", "d7d5", "e5d6"]:
            self.assertTrue(self.state.make_uci_move(uci)[0])
        self.assertEqual(self.state.captured_pieces["black"], ["p"])

        self.state.undo_move()
        self.assertEqual(self.state.captured_pieces["black"], [])
        # 黑方 d5 兵与白方 e5 兵均回到原位
        self.assertIn("3pP3", self.state.get_fen())

    def test_undo_last_move_property(self):
        self.assertIsNone(self.state.last_move)
        self.state.make_uci_move("e2e4")
        self.assertEqual(self.state.last_move.uci(), "e2e4")
        self.state.undo_move()
        self.assertIsNone(self.state.last_move)

    def test_import_pgn_roundtrip(self):
        for uci in ["e2e4", "e7e5", "g1f3", "b8c6"]:
            self.state.make_uci_move(uci)
        pgn_text = self.state.export_pgn()

        other = BoardState()
        self.assertTrue(other.import_pgn(pgn_text))
        self.assertEqual(other.get_fen(), self.state.get_fen())
        self.assertEqual(other.move_stack_san, self.state.move_stack_san)
        self.assertEqual(other.captured_pieces, {"white": [], "black": []})

    def test_import_pgn_rejects_illegal_moves(self):
        fake_pgn = '[Event "Test"]\n\n1. e4 e5 2. Ke4 *\n'
        fen_before = self.state.get_fen()
        self.assertFalse(self.state.import_pgn(fake_pgn))
        self.assertEqual(self.state.get_fen(), fen_before)

    def test_import_pgn_rejects_garbage(self):
        self.assertFalse(self.state.import_pgn("not a pgn at all"))

    def test_export_pgn_headers(self):
        for uci in ["e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"]:
            self.state.make_uci_move(uci)
        pgn_text = self.state.export_pgn()
        self.assertIn('[Result "1-0"]', pgn_text)
        self.assertNotIn("????.??.??", pgn_text)

    def test_reset_clears_everything(self):
        self.state.make_uci_move("e2e4")
        self.state.reset()
        self.assertEqual(self.state.get_fen(), chess.STARTING_FEN)
        self.assertEqual(self.state.move_stack_san, [])
        self.assertEqual(self.state.captured_pieces, {"white": [], "black": []})
        self.assertEqual(self.state.custom_headers["Date"], "????.??.??")

if __name__ == "__main__":
    unittest.main()
