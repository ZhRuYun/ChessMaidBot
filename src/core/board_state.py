"""
国际象棋规则核心与状态管理 (基于 python-chess 封装)
包含 Lichess 标准王车易位与双模式解析
"""
from typing import List, Optional, Tuple, Dict, Any
import chess
import chess.pgn
import io

class GameResult:
    IN_PROGRESS = "*"
    WHITE_WINS = "1-0"
    BLACK_WINS = "0-1"
    DRAW = "1/2-1/2"

class BoardState:
    """
    维护棋盘规则状态、走法合法性检验、特殊走法、状态历史及 PGN/FEN 导出
    """
    def __init__(self, fen: Optional[str] = None):
        self.board = chess.Board(fen) if fen else chess.Board()
        self.move_stack_san: List[str] = []
        self.captured_pieces: Dict[str, List[str]] = {"white": [], "black": []}
        self.custom_headers: Dict[str, str] = {
            "Event": "ChessMaidBot Casual Game",
            "Site": "Localhost",
            "Date": "????.??.??",
            "White": "Player 1",
            "Black": "Player 2",
        }

    def reset(self, fen: Optional[str] = None):
        """重置棋盘"""
        if fen:
            self.board = chess.Board(fen)
        else:
            self.board.reset()
        self.move_stack_san.clear()
        self.captured_pieces = {"white": [], "black": []}

    @property
    def turn(self) -> chess.Color:
        """当前行动方 (chess.WHITE 或 chess.BLACK)"""
        return self.board.turn

    @property
    def turn_name(self) -> str:
        return "White" if self.board.turn == chess.WHITE else "Black"

    @property
    def fullmove_number(self) -> int:
        return self.board.fullmove_number

    @property
    def halfmove_clock(self) -> int:
        return self.board.halfmove_clock

    def get_fen(self) -> str:
        """获取当前 FEN 字符串"""
        return self.board.fen()

    def get_piece_at(self, square: int) -> Optional[chess.Piece]:
        """获取指定格子上的棋子"""
        return self.board.piece_at(square)

    def is_legal(self, move: chess.Move) -> bool:
        """判定走法是否合法"""
        return move in self.board.legal_moves

    def get_legal_moves_from(self, from_square: int) -> List[chess.Move]:
        """获取指定格子上棋子的所有合法走法"""
        return [m for m in self.board.legal_moves if m.from_square == from_square]

    def resolve_castling_or_normal_move(self, from_sq: int, to_sq: int, promotion_piece=None) -> Optional[chess.Move]:
        """
        智能解析走法（完美支持标准走法与 Lichess 风格的点王再点车王车易位）
        """
        # 1. 优先检查是否是“点王再点车”的王车易位操作 (Lichess 交互)
        piece_from = self.board.piece_at(from_sq)
        piece_to = self.board.piece_at(to_sq)

        if piece_from and piece_from.piece_type == chess.KING and piece_from.color == self.board.turn:
            if piece_to and piece_to.piece_type == chess.ROOK and piece_to.color == self.board.turn:
                # 白方王车易位
                if self.board.turn == chess.WHITE and from_sq == chess.E1:
                    if to_sq == chess.H1:  # 白短易位 (e1 -> g1)
                        m = chess.Move(chess.E1, chess.G1)
                        if m in self.board.legal_moves:
                            return m
                    elif to_sq == chess.A1:  # 白长易位 (e1 -> c1)
                        m = chess.Move(chess.E1, chess.C1)
                        if m in self.board.legal_moves:
                            return m
                # 黑方王车易位
                elif self.board.turn == chess.BLACK and from_sq == chess.E8:
                    if to_sq == chess.H8:  # 黑短易位 (e8 -> g8)
                        m = chess.Move(chess.E8, chess.G8)
                        if m in self.board.legal_moves:
                            return m
                    elif to_sq == chess.A8:  # 黑长易位 (e8 -> c8)
                        m = chess.Move(chess.E8, chess.C8)
                        if m in self.board.legal_moves:
                            return m

        # 2. 常规走法或点王走到c/g列的标准易位
        direct_move = chess.Move(from_sq, to_sq, promotion=promotion_piece)
        if direct_move in self.board.legal_moves:
            return direct_move

        return None

    def is_promotion_move(self, from_square: int, to_square: int) -> bool:
        """检查该移动是否属于兵的升变走法"""
        piece = self.board.piece_at(from_square)
        if not piece or piece.piece_type != chess.PAWN:
            return False
        to_rank = chess.square_rank(to_square)
        return (piece.color == chess.WHITE and to_rank == 7) or (piece.color == chess.BLACK and to_rank == 0)

    def make_move(self, move: chess.Move) -> Tuple[bool, Optional[str], Optional[chess.Piece]]:
        """
        执行走法
        返回: (成功状态, SAN走法记谱, 被吃的棋子Piece对象)
        """
        if not self.is_legal(move):
            return False, None, None

        # 记录被吃子
        captured_piece = None
        if self.board.is_en_passant(move):
            captured_piece = chess.Piece(chess.PAWN, not self.board.turn)
        elif self.board.is_capture(move):
            captured_piece = self.board.piece_at(move.to_square)

        if captured_piece:
            cap_color_key = "white" if captured_piece.color == chess.WHITE else "black"
            self.captured_pieces[cap_color_key].append(captured_piece.symbol())

        san_str = self.board.san(move)
        self.board.push(move)
        self.move_stack_san.append(san_str)

        return True, san_str, captured_piece

    def make_uci_move(self, uci_str: str) -> Tuple[bool, Optional[str], Optional[chess.Piece]]:
        """通过 UCI 字符串落子"""
        try:
            move = chess.Move.from_uci(uci_str)
            return self.make_move(move)
        except Exception:
            return False, None, None

    def undo_move(self) -> Optional[chess.Move]:
        """悔棋一步"""
        if len(self.board.move_stack) == 0:
            return None
        last_move = self.board.pop()
        if self.move_stack_san:
            self.move_stack_san.pop()
        return last_move

    def is_check(self) -> bool:
        """是否处于被将军状态"""
        return self.board.is_check()

    def get_king_square(self, color: chess.Color) -> Optional[int]:
        """获取指定颜色王所在的格子"""
        return self.board.king(color)

    def is_game_over(self) -> bool:
        """对局是否结束"""
        return self.board.is_game_over()

    def get_game_status(self) -> Dict[str, Any]:
        """获取对局当前详细状态信息"""
        is_over = self.board.is_game_over()
        status_info = {
            "is_over": is_over,
            "is_check": self.board.is_check(),
            "is_checkmate": self.board.is_checkmate(),
            "is_stalemate": self.board.is_stalemate(),
            "is_insufficient_material": self.board.is_insufficient_material(),
            "is_seventyfive_moves": self.board.is_seventyfive_moves(),
            "is_fivefold_repetition": self.board.is_fivefold_repetition(),
            "can_claim_fifty_moves": self.board.can_claim_fifty_moves(),
            "can_claim_threefold_repetition": self.board.can_claim_threefold_repetition(),
            "result": GameResult.IN_PROGRESS,
            "reason": ""
        }

        if is_over:
            if self.board.is_checkmate():
                winner = "Black" if self.board.turn == chess.WHITE else "White"
                status_info["result"] = GameResult.BLACK_WINS if self.board.turn == chess.WHITE else GameResult.WHITE_WINS
                status_info["reason"] = f"Checkmate! {winner} wins."
            elif self.board.is_stalemate():
                status_info["result"] = GameResult.DRAW
                status_info["reason"] = "Draw by Stalemate (逼和)."
            elif self.board.is_insufficient_material():
                status_info["result"] = GameResult.DRAW
                status_info["reason"] = "Draw by Insufficient Material (子力不足)."
            elif self.board.is_seventyfive_moves():
                status_info["result"] = GameResult.DRAW
                status_info["reason"] = "Draw by 75-move rule."
            elif self.board.is_fivefold_repetition():
                status_info["result"] = GameResult.DRAW
                status_info["reason"] = "Draw by 5-fold repetition."
        return status_info

    def export_pgn(self) -> str:
        """导出当前对局为 PGN 格式文本"""
        game = chess.pgn.Game.from_board(self.board)
        for key, val in self.custom_headers.items():
            game.headers[key] = val
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
        return game.accept(exporter)

    def import_pgn(self, pgn_str: str) -> bool:
        """从 PGN 格式文本加载对局"""
        try:
            pgn_io = io.StringIO(pgn_str)
            game = chess.pgn.read_game(pgn_io)
            if game is None:
                return False
            self.board = game.board()
            self.move_stack_san.clear()
            for move in game.mainline_moves():
                self.make_move(move)
            return True
        except Exception:
            return False
