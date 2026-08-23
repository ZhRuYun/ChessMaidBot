"""
走法历史记录与记谱管理
"""
from typing import List, Tuple

class MoveRecord:
    def __init__(self, move_number: int, white_san: str, black_san: str = "", fen_after_white: str = "", fen_after_black: str = ""):
        self.move_number = move_number
        self.white_san = white_san
        self.black_san = black_san
        self.fen_after_white = fen_after_white
        self.fen_after_black = fen_after_black

class MoveHistoryManager:
    """管理对局走法列表与双栏记谱"""
    def __init__(self):
        self.records: List[MoveRecord] = []

    def clear(self):
        self.records.clear()

    def add_move(self, san: str, is_white: bool, fen: str):
        if is_white:
            move_num = len(self.records) + 1
            self.records.append(MoveRecord(move_num, white_san=san, fen_after_white=fen))
        else:
            if self.records:
                self.records[-1].black_san = san
                self.records[-1].fen_after_black = fen
            else:
                # 兼容从黑方回合初始化的局面
                self.records.append(MoveRecord(1, white_san="...", black_san=san, fen_after_black=fen))

    def pop_move(self) -> Tuple[bool, int]:
        """
        弹出最后一步走法
        返回: (是否删除了整行记录, 影响的行索引)
        """
        if not self.records:
            return False, -1
        last = self.records[-1]
        if last.black_san:
            last.black_san = ""
            last.fen_after_black = ""
            return False, len(self.records) - 1
        else:
            self.records.pop()
            return True, len(self.records)
