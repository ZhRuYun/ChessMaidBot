"""
开局库管理模块 (模块6 - 开局库组件)
支持:
  1. 基于 Lichess 开源开局库 (https://github.com/lichess-org/chess-openings) 的开局名称与 ECO 判定识别
  2. 候选走法推荐与权重读取
  3. 内置精选常用开局谱表与变例，支持优雅降级与本地 openings.json 自定义加载
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
import chess
import chess.polyglot

from ..config import BOOKS_DIR, OPENING_BOOK_PATH, DEFAULT_OPENINGS_JSON_PATH


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


# 内置精选开源常用开局库 (来自 lichess-org/chess-openings 精选子集)，无需外置下载即可即开即用
DEFAULT_OPENING_PATTERNS: Dict[str, Dict[str, Any]] = {
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -": {
        "eco": "A00",
        "name": "Starting Position (起始局面)",
        "moves": [
            {"uci": "e2e4", "san": "e4", "weight": 50, "comment": "King's Pawn (王兵开局 1. e4)"},
            {"uci": "d2d4", "san": "d4", "weight": 45, "comment": "Queen's Pawn (后兵开局 1. d4)"},
            {"uci": "c2c4", "san": "c4", "weight": 20, "comment": "English Opening (英国式开局 1. c4)"},
            {"uci": "g1f3", "san": "Nf3", "weight": 15, "comment": "Zukertort / Réti Opening (雷蒂开局 1. Nf3)"},
        ]
    },
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -": {
        "eco": "B00",
        "name": "King's Pawn Game",
        "moves": [
            {"uci": "e7e5", "san": "e5", "weight": 50, "comment": "Open Game"},
            {"uci": "c7c5", "san": "c5", "weight": 45, "comment": "Sicilian Defence (西西里防御)"},
            {"uci": "e7e6", "san": "e6", "weight": 30, "comment": "French Defence (法兰西防御)"},
            {"uci": "c7c6", "san": "c6", "weight": 25, "comment": "Caro-Kann Defence (卡罗-康防御)"},
            {"uci": "d7d6", "san": "d6", "weight": 15, "comment": "Pirc Defence (皮尔茨防御)"},
        ]
    },
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": {
        "eco": "C20",
        "name": "King's Pawn Game: Open Game",
        "moves": [
            {"uci": "g1f3", "san": "Nf3", "weight": 70, "comment": "King's Knight Opening"},
            {"uci": "f2f4", "san": "f4", "weight": 20, "comment": "King's Gambit (王翼弃兵)"},
            {"uci": "b1c3", "san": "Nc3", "weight": 15, "comment": "Vienna Game (维也纳开局)"},
            {"uci": "f1c4", "san": "Bc4", "weight": 15, "comment": "Bishop's Opening (象翼开局)"},
        ]
    },
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -": {
        "eco": "C40",
        "name": "King's Knight Opening",
        "moves": [
            {"uci": "b8c6", "san": "Nc6", "weight": 60, "comment": "Normal variation"},
            {"uci": "g8f6", "san": "Nf6", "weight": 35, "comment": "Petrov's Defence (俄罗斯防御)"},
            {"uci": "d7d6", "san": "d6", "weight": 15, "comment": "Philidor Defence (菲利多尔防御)"},
        ]
    },
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": {
        "eco": "C44",
        "name": "King's Knight Opening: Normal Variation",
        "moves": [
            {"uci": "f1b5", "san": "Bb5", "weight": 55, "comment": "Ruy Lopez (西班牙开局)"},
            {"uci": "f1c4", "san": "Bc4", "weight": 40, "comment": "Italian Game (意大利开局)"},
            {"uci": "d2d4", "san": "d4", "weight": 25, "comment": "Scotch Game (苏格兰开局)"},
            {"uci": "b1c3", "san": "Nc3", "weight": 20, "comment": "Four Knights Game (四骑士开局)"},
        ]
    },
    "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq -": {
        "eco": "C60",
        "name": "Ruy Lopez",
        "moves": [
            {"uci": "a7a6", "san": "a6", "weight": 65, "comment": "Morphy Defence (莫菲防御)"},
            {"uci": "g8f6", "san": "Nf6", "weight": 30, "comment": "Berlin Defence (柏林防御)"},
            {"uci": "f8c5", "san": "Bc5", "weight": 10, "comment": "Classical Defence"},
        ]
    },
    "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq -": {
        "eco": "C50",
        "name": "Italian Game",
        "moves": [
            {"uci": "f8c5", "san": "Bc5", "weight": 55, "comment": "Giuoco Piano (静局)"},
            {"uci": "g8f6", "san": "Nf6", "weight": 45, "comment": "Two Knights Defence (双骑士防御)"},
        ]
    },
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": {
        "eco": "B20",
        "name": "Sicilian Defence",
        "moves": [
            {"uci": "g1f3", "san": "Nf3", "weight": 70, "comment": "Open Sicilian"},
            {"uci": "b1c3", "san": "Nc3", "weight": 20, "comment": "Closed Sicilian"},
            {"uci": "c2c3", "san": "c3", "weight": 15, "comment": "Alapin Variation"},
        ]
    },
    "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq -": {
        "eco": "A40",
        "name": "Queen's Pawn Game",
        "moves": [
            {"uci": "d7d5", "san": "d5", "weight": 55, "comment": "Closed Game"},
            {"uci": "g8f6", "san": "Nf6", "weight": 45, "comment": "Indian Defence"},
            {"uci": "e7e6", "san": "e6", "weight": 20, "comment": "Horwitz Defence"},
            {"uci": "f7f5", "san": "f5", "weight": 15, "comment": "Dutch Defence"},
        ]
    },
    "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq -": {
        "eco": "D00",
        "name": "Queen's Pawn Game",
        "moves": [
            {"uci": "c2c4", "san": "c4", "weight": 65, "comment": "Queen's Gambit (后翼弃兵)"},
            {"uci": "g1f3", "san": "Nf3", "weight": 30, "comment": "London System / King's Knight"},
            {"uci": "c1f4", "san": "Bf4", "weight": 20, "comment": "London System (伦敦体系)"},
        ]
    },
    "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq -": {
        "eco": "D06",
        "name": "Queen's Gambit",
        "moves": [
            {"uci": "e7e6", "san": "e6", "weight": 55, "comment": "Queen's Gambit Declined (QGD)"},
            {"uci": "c7c6", "san": "c6", "weight": 40, "comment": "Slav Defence (斯拉夫防御)"},
            {"uci": "d5c4", "san": "dxc4", "weight": 25, "comment": "Queen's Gambit Accepted (QGA)"},
        ]
    },
}


class OpeningBook:
    """开局库管理器，专注于开局名称/ECO识别与走法推荐"""

    def __init__(self, book_path: Optional[Union[str, Path]] = None, json_path: Optional[Union[str, Path]] = None):
        self.book_path = Path(book_path) if book_path else OPENING_BOOK_PATH
        self.json_path = Path(json_path) if json_path else DEFAULT_OPENINGS_JSON_PATH
        self._custom_patterns: Dict[str, Dict[str, Any]] = {}
        self.reload()

    def reload(self):
        """加载外置 JSON 开局库 (Lichess openings 或自定义)，若不存在则使用内置谱表"""
        self._custom_patterns.clear()
        if self.json_path and self.json_path.exists() and self.json_path.is_file():
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    # 归一化 key 为 fen_core (前4字段)
                    for k, val in raw_data.items():
                        core_k = " ".join(k.split()[:4])
                        self._custom_patterns[core_k] = val
            except Exception:
                self._load_defaults()
        else:
            self._load_defaults()

    def _load_defaults(self):
        self._custom_patterns = {
            " ".join(k.split()[:4]): v for k, v in DEFAULT_OPENING_PATTERNS.items()
        }

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
        """从已加载的 Lichess / 内置谱表中检索走法"""
        fen_core = " ".join(board.fen().split()[:4])
        matched_info = self._custom_patterns.get(fen_core)
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

        # 1. 尝试从 Polyglot 库读取推荐走法
        poly_entries = self.get_entries_from_polyglot(board, limit=limit)
        
        # 2. 从 Lichess/内置谱表读取推荐走法
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

        # 获取开局 ECO / 名称 (通过 fen_core 匹配 Lichess 开局库)
        fen_core = " ".join(board.fen().split()[:4])
        info = self._custom_patterns.get(fen_core)
        if info:
            eco = info.get("eco", "A00")
            name = info.get("name", "Unknown Opening")
        else:
            eco = "A00"
            name = "Unknown Opening"

        return {
            "eco": eco,
            "name": name,
            "fen": board.fen(),
            "in_book": bool(info or combined_moves),
            "has_polyglot_book": self.has_polyglot_book(),
            "recommended_moves": combined_moves,
        }
