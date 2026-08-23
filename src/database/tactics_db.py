"""
EPD 战术编码库管理模块 (模块6 - 战术库组件)
支持:
  1. EPD (Extended Position Description) 标准格式解析与读取
  2. 战术题库管理 (包含开局陷阱、杀棋、双重打击、牵制、抽将、偏转等典型模式)
  3. 支持从本地自定义 .epd 题库文件动态加载
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
import chess

from ..config import TACTICS_DIR, DEFAULT_TACTICS_PATH


@dataclass
class TacticPuzzle:
    """战术题数据结构"""
    id: str
    fen: str
    bm: List[str]            # Best Move(s) - 最佳着法 (SAN 或 UCI)
    id_tag: str = ""         # 题目标识或主题
    theme: str = ""          # 战术主题分类 (如 mate, pin, fork, discovery)
    description: str = ""    # 战术解析或说明
    raw_epd: str = ""        # 原始 EPD 行


# 内置开源精选 EPD 战术题库 (遵循 CC0 / 开源无版权限制，标准 4 字段 EPD + opcodes)
DEFAULT_EPD_TACTICS = [
    # 1. 经典底线闷杀 (Smothered/Back-rank Mate)
    '6k1/5ppp/8/8/8/8/1Q4PP/6K1 w - - bm Qb8#; id "mate_in_1_backrank"; c0 "底线杀棋 (Back-rank Mate)";',
    'r1bqkb1r/pppp1ppp/2n5/4p3/2B1n3/5N2/PPPP1PPP/RNBQK2R w KQkq - bm Bxf7+; id "fork_tactic"; c0 "象破坏易位并展开攻势";',
    'r1b2rk1/ppp2ppp/8/3P4/2B1n3/8/PPP2PPP/RNBQ1RK1 b - - bm Nxf2; id "deflection"; c0 "打击防守要点";',
    'rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - bm d6; id "sicilian_main"; c0 "稳健控制中心";',
    'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - bm Ng5; id "fried_liver_attack"; c0 "炸肝攻击前奏，向 f7 施压";',
    # 2. 双重打击 (Fork)
    'r1b1k2r/pppp1ppp/5q2/4n3/3QP3/2N5/PPP2PPP/R3KB1R w KQkq - bm Nd5; id "knight_fork_threat"; c0 "骑士跃入中心发起多重威胁";',
    # 3. 牵制战术 (Pin)
    'rnbqk2r/ppp1bppp/4pn2/3p4/2PP4/2N2N2/PP2PPPP/R1BQKB1R w KQkq - bm Bg5; id "classical_pin"; c0 "利用白象对黑方 f6 骑士形成强力牵制";',
    # 4. 闪击/抽将 (Discovered Attack)
    'r1bqk1r/pppp1ppp/2n5/2b1P3/4n3/2P2N2/PP2PPPP/RNBQKB1R b KQkq - bm Bxf2#; id "scholar_mate_counter"; c0 "借由 f2 弱点一击必杀";',
    # 5. 残局兵升变通路 (Pawn breakthrough)
    '8/5k2/8/8/4P3/8/8/4K3 w - - bm Ke2; id "king_and_pawn_endgame"; c0 "王抢占关键格护送通路兵";'
]


class TacticsDatabase:
    """EPD 战术编码库管理器"""

    def __init__(self, epd_path: Optional[Union[str, Path]] = None):
        self.epd_path = Path(epd_path) if epd_path else DEFAULT_TACTICS_PATH
        self._puzzles: List[TacticPuzzle] = []
        self.reload()

    def reload(self):
        """重新加载内置与本地 EPD 题库"""
        self._puzzles.clear()

        # 1. 加载本地自定义 EPD 文件 (如果存在)
        if self.epd_path and self.epd_path.exists() and self.epd_path.is_file():
            try:
                content = self.epd_path.read_text(encoding="utf-8")
                for line in content.splitlines():
                    p = self.parse_epd_line(line)
                    if p:
                        self._puzzles.append(p)
            except Exception:
                pass

        # 2. 若本地无题库或解析为空，加载内置精选开源 EPD
        if not self._puzzles:
            for line in DEFAULT_EPD_TACTICS:
                p = self.parse_epd_line(line)
                if p:
                    self._puzzles.append(p)

    @staticmethod
    def parse_epd_line(epd_str: str) -> Optional[TacticPuzzle]:
        """解析单行 EPD 字符串
        标准格式示例: 6k1/5ppp/8/8/8/8/1Q4PP/6K1 w - - bm Qb8#; id "mate_1"; c0 "底线杀棋";
        """
        raw = epd_str.strip()
        if not raw or raw.startswith("#") or raw.startswith("%"):
            return None

        try:
            # 标准 EPD 格式为 4 字段基础局面 (pieces, turn, castling, ep) 紧跟 opcodes
            # 如果输入了带半步数/回合数的 6 字段 FEN (如 "... 0 1 bm ...")，自动清理这两个字段以适配 python-chess
            tokens = raw.split()
            if len(tokens) >= 6 and tokens[4].isdigit() and tokens[5].isdigit():
                clean_raw = " ".join(tokens[:4] + tokens[6:])
            else:
                clean_raw = raw

            board = chess.Board()
            ops = board.set_epd(clean_raw)
            fen = board.fen()

            # 解析 best moves (同时保留 SAN 与 UCI)
            bms = []
            if "bm" in ops:
                bm_val = ops["bm"]
                if isinstance(bm_val, list):
                    for m in bm_val:
                        if hasattr(m, "uci"):
                            try:
                                bms.append(board.san(m))
                            except Exception:
                                bms.append(m.uci())
                        else:
                            bms.append(str(m))
                else:
                    bms = [str(bm_val)]

            puzzle_id = str(ops.get("id", f"puzzle_{abs(hash(fen)) % 10000}"))
            comment = str(ops.get("c0", ops.get("comment", "")))
            
            # 推断战术主题
            theme = "tactics"
            if "mate" in puzzle_id.lower() or "mate" in comment.lower() or any("#" in str(b) for b in bms):
                theme = "checkmate"
            elif "pin" in puzzle_id.lower() or "pin" in comment.lower():
                theme = "pin"
            elif "fork" in puzzle_id.lower() or "fork" in comment.lower():
                theme = "fork"

            return TacticPuzzle(
                id=puzzle_id,
                fen=fen,
                bm=bms,
                id_tag=puzzle_id,
                theme=theme,
                description=comment,
                raw_epd=raw,
            )
        except Exception:
            return None

    def find_tactics_for_position(self, fen: str) -> Optional[TacticPuzzle]:
        """查找指定 FEN 是否在战术库中"""
        target_core = " ".join(fen.split()[:4])
        for p in self._puzzles:
            if " ".join(p.fen.split()[:4]) == target_core:
                return p
        return None

    def query_tactics(self, theme: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        """统一战术库检索接口"""
        results = []
        for p in self._puzzles:
            if theme and p.theme.lower() != theme.lower():
                continue
            results.append({
                "id": p.id,
                "fen": p.fen,
                "best_moves": p.bm,
                "theme": p.theme,
                "description": p.description,
            })
            if len(results) >= limit:
                break

        return {
            "category": "tactics",
            "total_available": len(self._puzzles),
            "count": len(results),
            "theme_filter": theme or "all",
            "puzzles": results,
        }
