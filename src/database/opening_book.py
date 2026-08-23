"""
开局库管理模块 (模块6 - 开局库组件)
支持:
  1. 基于标准开源 Polyglot 格式 (.bin) 的开局走法与权重检索
  2. 开源 ECO (Encyclopaedia of Chess Openings) 局面命名与分类库
  3. 内置精选常用开局谱表与变例，支持优雅降级与本地自定义加载
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
import chess
import chess.polyglot

from ..config import BOOKS_DIR, OPENING_BOOK_PATH


@dataclass
class OpeningMoveEntry:
    """开局走法条目"""
    uci: str
    san: str
    weight: int
    learn: int = 0
    comment: str = ""


@dataclass
class OpeningInfo:
    """开局判定信息"""
    eco: str
    name: str
    fen: str
    moves_san: List[str]


# 内置精选开源常用开局库 (遵循 CC0 / Public Domain 谱表), 无需额外二进制即可即开即用
DEFAULT_OPENING_PATTERNS: Dict[str, Dict[str, Any]] = {
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1": {
        "eco": "B00",
        "name": "King's Pawn Game (王兵开局)",
        "moves": [
            {"uci": "e7e5", "san": "e5", "weight": 50, "comment": "Open Game (开放性对局)"},
            {"uci": "c7c5", "san": "c5", "weight": 45, "comment": "Sicilian Defence (西西里防御)"},
            {"uci": "e7e6", "san": "e6", "weight": 30, "comment": "French Defence (法兰西防御)"},
            {"uci": "c7c6", "san": "c6", "weight": 25, "comment": "Caro-Kann Defence (卡罗-康防御)"},
            {"uci": "d7d6", "san": "d6", "weight": 15, "comment": "Pirc Defence (皮尔茨防御)"},
        ]
    },
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2": {
        "eco": "C20",
        "name": "King's Pawn Game: Open Game",
        "moves": [
            {"uci": "g1f3", "san": "Nf3", "weight": 70, "comment": "King's Knight Opening"},
            {"uci": "f2f4", "san": "f4", "weight": 20, "comment": "King's Gambit (王翼弃兵)"},
            {"uci": "b1c3", "san": "Nc3", "weight": 15, "comment": "Vienna Game (维也纳开局)"},
            {"uci": "f1c4", "san": "Bc4", "weight": 15, "comment": "Bishop's Opening (象翼开局)"},
        ]
    },
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2": {
        "eco": "C40",
        "name": "King's Knight Opening",
        "moves": [
            {"uci": "b8c6", "san": "Nc6", "weight": 60, "comment": "Main line, defending e5"},
            {"uci": "g8f6", "san": "Nf6", "weight": 35, "comment": "Petrov's Defence (彼得罗夫防御/俄罗斯防御)"},
            {"uci": "d7d6", "san": "d6", "weight": 15, "comment": "Philidor Defence (菲利多尔防御)"},
        ]
    },
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3": {
        "eco": "C44",
        "name": "King's Knight Opening: Normal Variation",
        "moves": [
            {"uci": "f1b5", "san": "Bb5", "weight": 55, "comment": "Ruy Lopez / Spanish Opening (西班牙开局)"},
            {"uci": "f1c4", "san": "Bc4", "weight": 40, "comment": "Italian Game (意大利开局)"},
            {"uci": "d2d4", "san": "d4", "weight": 25, "comment": "Scotch Game (苏格兰开局)"},
            {"uci": "b1c3", "san": "Nc3", "weight": 20, "comment": "Four Knights Game (四骑士开局)"},
        ]
    },
    "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3": {
        "eco": "C60",
        "name": "Ruy Lopez (西班牙开局)",
        "moves": [
            {"uci": "a7a6", "san": "a6", "weight": 65, "comment": "Morphy Defence (莫菲防御)"},
            {"uci": "g8f6", "san": "Nf6", "weight": 30, "comment": "Berlin Defence (柏林防御)"},
            {"uci": "f8c5", "san": "Bc5", "weight": 10, "comment": "Classical Defence"},
        ]
    },
    "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3": {
        "eco": "C50",
        "name": "Italian Game (意大利开局 / Giuoco Piano)",
        "moves": [
            {"uci": "f8c5", "san": "Bc5", "weight": 55, "comment": "Giuoco Piano (静局)"},
            {"uci": "g8f6", "san": "Nf6", "weight": 45, "comment": "Two Knights Defence (双骑士防御)"},
        ]
    },
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2": {
        "eco": "B20",
        "name": "Sicilian Defence (西西里防御)",
        "moves": [
            {"uci": "g1f3", "san": "Nf3", "weight": 70, "comment": "Open Sicilian setup"},
            {"uci": "b1c3", "san": "Nc3", "weight": 20, "comment": "Closed Sicilian (封闭西西里)"},
            {"uci": "c2c3", "san": "c3", "weight": 15, "comment": "Alapin Variation (阿拉平变例)"},
        ]
    },
    "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1": {
        "eco": "A40",
        "name": "Queen's Pawn Game (后兵开局)",
        "moves": [
            {"uci": "d7d5", "san": "d5", "weight": 55, "comment": "Closed Game (封闭性对局)"},
            {"uci": "g8f6", "san": "Nf6", "weight": 45, "comment": "Indian Defences (印度防御群)"},
            {"uci": "e7e6", "san": "e6", "weight": 20, "comment": "Horwitz Defence / French Transposition"},
            {"uci": "f7f5", "san": "f5", "weight": 15, "comment": "Dutch Defence (荷兰防御)"},
        ]
    },
    "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2": {
        "eco": "D00",
        "name": "Queen's Pawn Game",
        "moves": [
            {"uci": "c2c4", "san": "c4", "weight": 65, "comment": "Queen's Gambit (后翼弃兵)"},
            {"uci": "g1f3", "san": "Nf3", "weight": 30, "comment": "King's Knight / London System setup"},
            {"uci": "c1f4", "san": "Bf4", "weight": 20, "comment": "London System (伦敦体系)"},
        ]
    },
    "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 0 2": {
        "eco": "D06",
        "name": "Queen's Gambit (后翼弃兵)",
        "moves": [
            {"uci": "e7e6", "san": "e6", "weight": 55, "comment": "Queen's Gambit Declined - QGD (拒后翼弃兵)"},
            {"uci": "c7c6", "san": "c6", "weight": 40, "comment": "Slav Defence (斯拉夫防御)"},
            {"uci": "d5c4", "san": "dxc4", "weight": 25, "comment": "Queen's Gambit Accepted - QGA (应后翼弃兵)"},
        ]
    },
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1": {
        "eco": "A00",
        "name": "Starting Position (起始局面)",
        "moves": [
            {"uci": "e2e4", "san": "e4", "weight": 50, "comment": "King's Pawn (王兵开局 1. e4)"},
            {"uci": "d2d4", "san": "d4", "weight": 45, "comment": "Queen's Pawn (后兵开局 1. d4)"},
            {"uci": "c2c4", "san": "c4", "weight": 20, "comment": "English Opening (英国式开局 1. c4)"},
            {"uci": "g1f3", "san": "Nf3", "weight": 15, "comment": "Zukertort / Réti Opening (雷蒂开局 1. Nf3)"},
        ]
    },
}


class OpeningBook:
    """开局库管理器，支持 Polyglot 二进制库与内置开源开局库无缝组合"""

    def __init__(self, book_path: Optional[Union[str, Path]] = None):
        self.book_path = Path(book_path) if book_path else OPENING_BOOK_PATH
        self._custom_patterns: Dict[str, Dict[str, Any]] = dict(DEFAULT_OPENING_PATTERNS)

    def has_polyglot_book(self) -> bool:
        """检测本地是否存在 Polyglot 格式开局库文件"""
        return self.book_path is not None and self.book_path.exists() and self.book_path.is_file()

    def get_entries_from_polyglot(self, board: chess.Board, limit: int = 5) -> List[OpeningMoveEntry]:
        """从本地 Polyglot (.bin) 文件中检索走法"""
        if not self.has_polyglot_book():
            return []

        entries = []
        try:
            with chess.polyglot.open_reader(str(self.book_path)) as reader:
                poly_entries = list(reader.find_all(board))
                # 按权重从大到小排序
                poly_entries.sort(key=lambda e: e.weight, reverse=True)
                for entry in poly_entries[:limit]:
                    move = entry.move
                    if move in board.legal_moves:
                        san = board.san(move)
                        entries.append(OpeningMoveEntry(
                            uci=move.uci(),
                            san=san,
                            weight=entry.weight,
                            learn=entry.learn,
                            comment="Polyglot Opening Book",
                        ))
        except Exception:
            return []
        return entries

    def get_entries_from_builtin(self, board: chess.Board, limit: int = 5) -> List[OpeningMoveEntry]:
        """从内置开源谱表中检索走法"""
        fen_key = board.fen()
        # 兼容只匹配前4个FEN字段 (棋子、走子方、易位权、过路兵)
        fen_core = " ".join(fen_key.split()[:4])
        matched_info = None

        if fen_key in self._custom_patterns:
            matched_info = self._custom_patterns[fen_key]
        else:
            for pat_fen, info in self._custom_patterns.items():
                if " ".join(pat_fen.split()[:4]) == fen_core:
                    matched_info = info
                    break

        if not matched_info:
            return []

        entries = []
        for m in matched_info.get("moves", []):
            try:
                move = chess.Move.from_uci(m["uci"])
                if move in board.legal_moves:
                    entries.append(OpeningMoveEntry(
                        uci=m["uci"],
                        san=m.get("san", board.san(move)),
                        weight=m.get("weight", 10),
                        comment=m.get("comment", ""),
                    ))
            except Exception:
                continue

        entries.sort(key=lambda e: e.weight, reverse=True)
        return entries[:limit]

    def query_opening(self, board_or_fen: Union[chess.Board, str], limit: int = 5) -> Dict[str, Any]:
        """统一开局查询接口：
        返回当前局面的开局名称、ECO 编码、推荐候选着法列表
        """
        if isinstance(board_or_fen, str):
            board = chess.Board(board_or_fen)
        else:
            board = board_or_fen.copy()

        # 1. 尝试从 Polyglot 库读取
        poly_entries = self.get_entries_from_polyglot(board, limit=limit)
        
        # 2. 内置谱表读取
        builtin_entries = self.get_entries_from_builtin(board, limit=limit)

        # 合并推荐走法，优先展示 Polyglot 结果
        combined_moves = []
        seen_uci = set()
        for e in poly_entries + builtin_entries:
            if e.uci not in seen_uci:
                seen_uci.add(e.uci)
                combined_moves.append({
                    "uci": e.uci,
                    "san": e.san,
                    "weight": e.weight,
                    "comment": e.comment,
                })
            if len(combined_moves) >= limit:
                break

        # 获取开局 ECO / 名称
        eco = "A00"
        name = "Unknown Opening"
        fen_core = " ".join(board.fen().split()[:4])
        for pat_fen, info in self._custom_patterns.items():
            if " ".join(pat_fen.split()[:4]) == fen_core:
                eco = info.get("eco", "A00")
                name = info.get("name", "Unknown Opening")
                break

        return {
            "eco": eco,
            "name": name,
            "fen": board.fen(),
            "in_book": len(combined_moves) > 0,
            "has_polyglot_book": self.has_polyglot_book(),
            "recommended_moves": combined_moves,
        }
