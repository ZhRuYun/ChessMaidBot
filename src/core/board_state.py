"""
国际象棋规则核心与状态管理 (基于 python-chess 封装) - 模块3
维护棋盘规则、走法合法性、特殊走法、吃子记录及 PGN/FEN 导入导出
"""
from datetime import date
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
    """棋盘规则状态的唯一权威数据源 (只通过本类写棋局)"""

    def __init__(self, fen: Optional[str] = None):
        self.board = chess.Board(fen) if fen else chess.Board()
        self.move_stack_san: List[str] = []
        self.captured_pieces: Dict[str, List[str]] = {"white": [], "black": []}
        self.custom_headers: Dict[str, str] = self._default_headers()

    @staticmethod
    def _default_headers() -> Dict[str, str]:
        return {
            "Event": "ChessMaidBot Casual Game",
            "Site": "Localhost",
            "Date": "????.??.??",
            "White": "Player 1",
            "Black": "Player 2",
        }

    def reset(self, fen: Optional[str] = None):
        """重置棋盘、记谱、吃子记录与对局头信息"""
        self.board = chess.Board(fen) if fen else chess.Board()
        self.move_stack_san.clear()
        self.captured_pieces = {"white": [], "black": []}
        self.custom_headers = self._default_headers()

    @property
    def turn(self) -> chess.Color:
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

    @property
    def last_move(self) -> Optional[chess.Move]:
        """最近一步走法 (无走法时为 None)"""
        return self.board.peek() if self.board.move_stack else None

    def get_fen(self) -> str:
        return self.board.fen()

    def get_piece_at(self, square: int) -> Optional[chess.Piece]:
        return self.board.piece_at(square)

    def is_legal(self, move: chess.Move) -> bool:
        return move in self.board.legal_moves

    def legal_move_count(self) -> int:
        return self.board.legal_moves.count()

    def get_legal_moves_from(self, from_square: int) -> List[chess.Move]:
        return [m for m in self.board.legal_moves if m.from_square == from_square]

    def resolve_castling_or_normal_move(self, from_sq: int, to_sq: int, promotion_piece=None) -> Optional[chess.Move]:
        """解析走法: 支持 Lichess 风格点王再点车易位, 以及标准走法"""
        piece_from = self.board.piece_at(from_sq)
        piece_to = self.board.piece_at(to_sq)

        if piece_from and piece_from.piece_type == chess.KING and piece_from.color == self.board.turn:
            if piece_to and piece_to.piece_type == chess.ROOK and piece_to.color == self.board.turn:
                if self.board.turn == chess.WHITE and from_sq == chess.E1:
                    king_target = {"h1": chess.G1, "a1": chess.C1}.get(chess.square_name(to_sq))
                elif self.board.turn == chess.BLACK and from_sq == chess.E8:
                    king_target = {"h8": chess.G8, "a8": chess.C8}.get(chess.square_name(to_sq))
                else:
                    king_target = None
                if king_target is not None:
                    m = chess.Move(from_sq, king_target)
                    if m in self.board.legal_moves:
                        return m

        direct_move = chess.Move(from_sq, to_sq, promotion=promotion_piece)
        if direct_move in self.board.legal_moves:
            return direct_move
        return None

    def is_promotion_move(self, from_square: int, to_square: int) -> bool:
        piece = self.board.piece_at(from_square)
        if not piece or piece.piece_type != chess.PAWN:
            return False
        to_rank = chess.square_rank(to_square)
        return (piece.color == chess.WHITE and to_rank == 7) or (piece.color == chess.BLACK and to_rank == 0)

    def _captured_piece_of(self, move: chess.Move) -> Optional[chess.Piece]:
        """走法对应的被吃棋子 (不含走子方自身), 吃过路兵返回兵"""
        if self.board.is_en_passant(move):
            return chess.Piece(chess.PAWN, not self.board.turn)
        if self.board.is_capture(move):
            return self.board.piece_at(move.to_square)
        return None

    @staticmethod
    def _capture_color_key(piece: chess.Piece) -> str:
        return "white" if piece.color == chess.WHITE else "black"

    def make_move(self, move: chess.Move) -> Tuple[bool, Optional[str], Optional[chess.Piece]]:
        """执行走法, 返回 (成功, SAN, 被吃棋子)"""
        if not self.is_legal(move):
            return False, None, None

        captured_piece = self._captured_piece_of(move)
        if captured_piece:
            self.captured_pieces[self._capture_color_key(captured_piece)].append(captured_piece.symbol())

        san_str = self.board.san(move)
        self.board.push(move)
        self.move_stack_san.append(san_str)
        return True, san_str, captured_piece

    def make_uci_move(self, uci_str: str) -> Tuple[bool, Optional[str], Optional[chess.Piece]]:
        try:
            move = chess.Move.from_uci(uci_str)
        except ValueError:
            return False, None, None
        return self.make_move(move)

    def undo_move(self) -> Optional[chess.Move]:
        """悔棋一步, 同步恢复记谱与吃子记录"""
        if not self.board.move_stack:
            return None

        last_move = self.board.peek()
        self.board.pop()
        if self.move_stack_san:
            self.move_stack_san.pop()

        # pop 后局面回到走法之前, 可直接复用被吃子判定逻辑
        captured = self._captured_piece_of(last_move)
        if captured:
            key = self._capture_color_key(captured)
            if self.captured_pieces[key]:
                self.captured_pieces[key].pop()
        return last_move

    def is_check(self) -> bool:
        return self.board.is_check()

    def get_king_square(self, color: chess.Color) -> Optional[int]:
        return self.board.king(color)

    def is_game_over(self) -> bool:
        return self.board.is_game_over()

    def get_game_status(self) -> Dict[str, Any]:
        """对局当前状态详情 (终局原因/结果)"""
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
            "reason": "",
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
        """导出当前对局为 PGN, 自动补全 Date 占位符与 Result 头"""
        headers = dict(self.custom_headers)
        if headers.get("Date", "").startswith("????"):
            headers["Date"] = date.today().strftime("%Y.%m.%d")

        game = chess.pgn.Game.from_board(self.board)
        status = self.get_game_status()
        headers["Result"] = status["result"]
        for key, val in headers.items():
            game.headers[key] = val

        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
        return game.accept(exporter)

    def import_pgn(self, pgn_str: str) -> bool:
        """从 PGN 文本加载对局 (含头信息); 含错误/空棋谱时拒绝并保持原局面"""
        try:
            game = chess.pgn.read_game(io.StringIO(pgn_str))
        except Exception:
            return False
        if game is None or game.errors:
            return False
        if not any(game.mainline_moves()):
            return False

        saved_state = (self.board, list(self.move_stack_san), dict(self.captured_pieces), dict(self.custom_headers))
        try:
            self.board = game.board()
            self.move_stack_san = []
            self.captured_pieces = {"white": [], "black": []}
            self.custom_headers = self._default_headers()
            for key, val in game.headers.items():
                if val:
                    self.custom_headers[key] = val
            for move in game.mainline_moves():
                ok, _, _ = self.make_move(move)
                if not ok:
                    raise ValueError(f"非法走法: {move.uci()}")
            return True
        except Exception:
            self.board, self.move_stack_san, self.captured_pieces, self.custom_headers = saved_state
            return False
