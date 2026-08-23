"""
历史棋局库 (模块6) - 终局对局以 PGN 文件形式持久化
面向 LLM 读取设计 (纯文本 PGN), 不考虑 Stockfish 读取;
开局库/战术库/残局库后续在本包内扩展
"""
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..config import GAMES_DIR


class HistoryStore:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else GAMES_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def save_game(self, pgn_text: str, result: str = "*") -> Path:
        """保存一局 PGN, 返回文件路径"""
        safe_result = result.replace("/", "-").replace(" ", "")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.root / f"{stamp}-{safe_result}.pgn"
        counter = 1
        while path.exists():
            path = self.root / f"{stamp}-{safe_result}-{counter}.pgn"
            counter += 1
        path.write_text(pgn_text, encoding="utf-8")
        return path

    def list_games(self) -> List[Path]:
        return sorted(self.root.glob("*.pgn"))

    @staticmethod
    def load_text(path: Path) -> str:
        return Path(path).read_text(encoding="utf-8")
