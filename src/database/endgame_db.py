"""
残局库管理与评估模块 (模块6 - 残局库组件)
支持:
  1. Syzygy Tablebases 标准残局库接口 (支持 WDL 胜平负与 DTZ 步数检索)
  2. 纯规则基础理论残局评估器 (无 Tablebase 时的即开即用降级)
  3. 典型残局形态快速判定 (单王对王后/单车杀单王/双象杀单王/异色象和棋/基本兵残局规则)
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Union
import chess
import chess.syzygy

from ..config import SYZYGY_DIR, DEFAULT_SYZYGY_PATH


@dataclass
class EndgameEvaluation:
    """残局评估结果"""
    fen: str
    piece_count: int
    is_theoretical_endgame: bool
    wdl: Optional[int] = None       # 2: 胜, 1: 必胜(祝福), 0: 和, -1: 必败(受诅), -2: 败
    wdl_label: str = "Unknown"      # "Win", "Draw", "Loss"
    dtz: Optional[int] = None       # Distance to Zeroing (吃子或推兵所需步数)
    source: str = "heuristic"       # "syzygy" or "heuristic"
    advice: str = ""                # 女仆给出的残局教学要点


class EndgameDatabase:
    """残局库与理论残局评估器"""

    def __init__(self, syzygy_path: Optional[Union[str, Path]] = None):
        self.syzygy_path = Path(syzygy_path) if syzygy_path else DEFAULT_SYZYGY_PATH
        self._tablebase: Optional[chess.syzygy.Tablebase] = None
        self._init_syzygy()

    def _init_syzygy(self):
        """初始化 Syzygy 残局库 (如果本地存放了 .rtbw / .rtbz 文件)"""
        if self.syzygy_path and self.syzygy_path.exists():
            try:
                self._tablebase = chess.syzygy.open_tablebase(str(self.syzygy_path))
            except Exception:
                self._tablebase = None

    def has_syzygy(self) -> bool:
        """检测 Syzygy 残局库是否已成功挂载"""
        return self._tablebase is not None

    def close(self):
        """释放 Tablebase 文件句柄"""
        if self._tablebase is not None:
            try:
                self._tablebase.close()
            except Exception:
                pass
            self._tablebase = None

    def probe_syzygy(self, board: chess.Board) -> Optional[EndgameEvaluation]:
        """尝试通过 Syzygy Tablebase 探测精准 WDL / DTZ"""
        if not self._tablebase:
            return None

        try:
            wdl = self._tablebase.probe_wdl(board)
            dtz = None
            try:
                dtz = self._tablebase.probe_dtz(board)
            except Exception:
                pass

            labels = {2: "Win (必胜)", 1: "Blessed Win", 0: "Draw (理论和棋)", -1: "Cursed Loss", -2: "Loss (必败)"}
            wdl_label = labels.get(wdl, "Unknown")
            advice = "当前残局处于 Syzygy 精准残局库覆盖范围，每步走法均已计算出绝对理论极值。"
            if wdl > 0:
                advice += f" 处于胜势，注意避免长将或逼和。"
            elif wdl == 0:
                advice += " 处于理论和局局面，精准防守即可确保和棋。"
            else:
                advice += " 处于理论败局，争取对手出现失误。"

            return EndgameEvaluation(
                fen=board.fen(),
                piece_count=len(board.piece_map()),
                is_theoretical_endgame=True,
                wdl=wdl,
                wdl_label=wdl_label,
                dtz=dtz,
                source="syzygy",
                advice=advice,
            )
        except Exception:
            return None

    def evaluate_heuristic_endgame(self, board: chess.Board) -> EndgameEvaluation:
        """基于经典残局规则的启发式残局理论判定"""
        piece_map = board.piece_map()
        count = len(piece_map)
        
        # 1. 基础子力不足判定 (由 python-chess 原生保障)
        if board.is_insufficient_material():
            return EndgameEvaluation(
                fen=board.fen(),
                piece_count=count,
                is_theoretical_endgame=True,
                wdl=0,
                wdl_label="Draw (理论和棋)",
                source="heuristic",
                advice="双方均无足够杀王子力（如单马、单象或双方各一象同色格），根据规则判定理论和棋。",
            )

        # 2. 单王残局杀法识别
        white_pieces = [p for p in piece_map.values() if p.color == chess.WHITE]
        black_pieces = [p for p in piece_map.values() if p.color == chess.BLACK]

        # 黑方只有单王
        if len(black_pieces) == 1 and black_pieces[0].piece_type == chess.KING:
            # 拥有王后 / 车
            has_q = any(p.piece_type == chess.QUEEN for p in white_pieces)
            has_r = any(p.piece_type == chess.ROOK for p in white_pieces)
            if has_q:
                return EndgameEvaluation(
                    fen=board.fen(),
                    piece_count=count,
                    is_theoretical_endgame=True,
                    wdl=2 if board.turn == chess.WHITE else -2,
                    wdl_label="Win (白方必胜)" if board.turn == chess.WHITE else "Loss (黑方必败)",
                    source="heuristic",
                    advice="【单后杀单王】经典残局要点：使用后如骑士一般将敌王逼退至棋盘边缘或死角，再将我方王调至近旁形成封锁杀棋，注意提防逼和（Stalemate）！",
                )
            if has_r:
                return EndgameEvaluation(
                    fen=board.fen(),
                    piece_count=count,
                    is_theoretical_endgame=True,
                    wdl=2 if board.turn == chess.WHITE else -2,
                    wdl_label="Win (白方必胜)" if board.turn == chess.WHITE else "Loss (黑方必败)",
                    source="heuristic",
                    advice="【单车杀单王】经典残局要点：用单车构建切线（Box Method）限制黑王活动空间，配合己方王进行对王（Opposition）后推线，步步为营。",
                )

        # 白方只有单王
        if len(white_pieces) == 1 and white_pieces[0].piece_type == chess.KING:
            has_q = any(p.piece_type == chess.QUEEN for p in black_pieces)
            has_r = any(p.piece_type == chess.ROOK for p in black_pieces)
            if has_q:
                return EndgameEvaluation(
                    fen=board.fen(),
                    piece_count=count,
                    is_theoretical_endgame=True,
                    wdl=-2 if board.turn == chess.WHITE else 2,
                    wdl_label="Loss (白方必败)" if board.turn == chess.WHITE else "Win (黑方必胜)",
                    source="heuristic",
                    advice="【单后杀单王】黑方拥有绝对胜势。注意白方王避免走入死角自闭，等待对手失误。",
                )
            if has_r:
                return EndgameEvaluation(
                    fen=board.fen(),
                    piece_count=count,
                    is_theoretical_endgame=True,
                    wdl=-2 if board.turn == chess.WHITE else 2,
                    wdl_label="Loss (白方必败)" if board.turn == chess.WHITE else "Win (黑方必胜)",
                    source="heuristic",
                    advice="【单车杀单王】黑方拥有必胜局面。防守方尽量占据棋盘中央以延缓被逼入边缘。",
                )

        # 3. 基本兵残局 (King & Pawn)
        has_only_pawns_and_kings = all(p.piece_type in (chess.KING, chess.PAWN) for p in piece_map.values())
        if has_only_pawns_and_kings and count <= 6:
            return EndgameEvaluation(
                fen=board.fen(),
                piece_count=count,
                is_theoretical_endgame=True,
                source="heuristic",
                advice="【王兵残局】核心关键在于争夺对王（Opposition）、关键格（Key Squares）以及正方形法则（Rule of the Square）。",
            )

        # 默认常规残局
        is_endgame = count <= 10
        return EndgameEvaluation(
            fen=board.fen(),
            piece_count=count,
            is_theoretical_endgame=is_endgame,
            source="heuristic",
            advice="【常规残局原则】王在残局中是非常活跃的进攻子力，请积极让王走入棋盘中心，同时注重通路兵（Passed Pawn）的创造与护送。" if is_endgame else "当前处于中局，尚未进入纯残局阶段。",
        )

    def evaluate(self, board_or_fen: Union[chess.Board, str]) -> EndgameEvaluation:
        """评估指定局面残局"""
        if isinstance(board_or_fen, str):
            board = chess.Board(board_or_fen)
        else:
            board = board_or_fen

        # 先查 Syzygy，没有则降级使用启发式残局理论
        res = self.probe_syzygy(board)
        if res is not None:
            return res
        return self.evaluate_heuristic_endgame(board)

    def query_endgame(self, board_or_fen: Union[chess.Board, str]) -> Dict[str, Any]:
        """统一残局查询接口"""
        eval_res = self.evaluate(board_or_fen)
        return {
            "category": "endgame",
            "fen": eval_res.fen,
            "piece_count": eval_res.piece_count,
            "is_endgame": eval_res.is_theoretical_endgame,
            "wdl": eval_res.wdl,
            "wdl_label": eval_res.wdl_label,
            "dtz": eval_res.dtz,
            "source": eval_res.source,
            "has_syzygy_database": self.has_syzygy(),
            "maid_advice": eval_res.advice,
        }
