"""
走法历史记录与双栏记谱管理 (模块3) - 记谱的单一数据源
每条记录附带 FEN 快照，维护对局走法与局面演进
"""
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class MoveRecord:
    move_number: int
    white_san: str = ""
    black_san: str = ""
    fen_after_white: str = ""
    fen_after_black: str = ""


class MoveHistoryManager:
    """管理对局走法列表与双栏记谱"""

    def __init__(self):
        self.records: List[MoveRecord] = []

    def clear(self):
        self.records.clear()

    @property
    def move_count(self) -> int:
        return len(self.records)

    def add_move(self, san: str, is_white: bool, fen: str):
        """按行棋方追加一步; 支持从黑方回合开局 (白方栏显示 ...)"""
        if is_white:
            self.records.append(
                MoveRecord(move_number=len(self.records) + 1, white_san=san, fen_after_white=fen)
            )
        else:
            if self.records and self.records[-1].black_san == "":
                self.records[-1].black_san = san
                self.records[-1].fen_after_black = fen
            else:
                self.records.append(
                    MoveRecord(move_number=1, white_san="...", black_san=san, fen_after_black=fen)
                )

    def pop_move(self) -> Tuple[bool, int]:
        """
        弹出最后一步走法
        返回: (是否删除了整行记录, 受影响的行索引)
        """
        if not self.records:
            return False, -1

        last = self.records[-1]
        # 黑先开局的占位行 ("...") 没有独立的白方着法, 直接整行删除
        if last.black_san and last.white_san not in ("", "..."):
            last.black_san = ""
            last.fen_after_black = ""
            return False, len(self.records) - 1

        self.records.pop()
        return True, len(self.records)

    def last_san(self) -> Optional[str]:
        """最近一步的 SAN (空局返回 None)"""
        if not self.records:
            return None
        last = self.records[-1]
        return last.black_san or last.white_san
