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

    def test_legal_moves(self):
        move = chess.Move.from_uci("e2e4")
        self.assertTrue(self.state.is_legal(move))
        
        illegal_move = chess.Move.from_uci("e2e5")
        self.assertFalse(self.state.is_legal(illegal_move))

    def test_lichess_style_castling_kingside(self):
        # 设置已清空王翼的白方易位局面
        self.state.reset("r1bqk2r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        # 既支持 E1 -> G1
        m_std = self.state.resolve_castling_or_normal_move(chess.E1, chess.G1)
        self.assertIsNotNone(m_std)
        self.assertEqual(m_std.uci(), "e1g1")
        
        # 也支持 Lichess 风格: 点王 (E1) 再点车 (H1)
        m_lichess = self.state.resolve_castling_or_normal_move(chess.E1, chess.H1)
        self.assertIsNotNone(m_lichess)
        self.assertEqual(m_lichess.uci(), "e1g1")

    def test_lichess_style_castling_queenside(self):
        # 设置已清空后翼的白方易位局面
        self.state.reset("r3k2r/pppq1ppp/2npbn2/4p3/4P3/2NPBN2/PPPQ1PPP/R3K2R w KQkq - 6 8")
        # 点王 (E1) 再点后翼车 (A1)
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

if __name__ == "__main__":
    unittest.main()
