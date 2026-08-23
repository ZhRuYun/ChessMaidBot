"""
统一数据库管理器 (模块6 - Unified Database Manager)
将历史棋局库、开局库、EPD 战术编码库、残局库聚合在单一入口下，统一管理 data/ 大目录中的所有子库
"""
from pathlib import Path
from typing import Optional, Dict, Any, Union

from ..config import DATA_DIR, GAMES_DIR, BOOKS_DIR, TACTICS_DIR, SYZYGY_DIR, OPENING_BOOK_PATH, DEFAULT_TACTICS_PATH, DEFAULT_SYZYGY_PATH
from .history_store import HistoryStore
from .opening_book import OpeningBook
from .tactics_db import TacticsDatabase
from .endgame_db import EndgameDatabase


class UnifiedDatabase:
    """统一数据库大目录管理器"""

    def __init__(
        self,
        base_data_dir: Optional[Union[str, Path]] = None,
        opening_book_path: Optional[Union[str, Path]] = None,
        tactics_path: Optional[Union[str, Path]] = None,
        syzygy_path: Optional[Union[str, Path]] = None,
    ):
        self.data_dir = Path(base_data_dir) if base_data_dir else DATA_DIR
        self.games_dir = self.data_dir / "games"
        self.books_dir = self.data_dir / "books"
        self.tactics_dir = self.data_dir / "tactics"
        self.syzygy_dir = self.data_dir / "syzygy"

        # 确保全部子目录存在
        for d in (self.data_dir, self.games_dir, self.books_dir, self.tactics_dir, self.syzygy_dir):
            d.mkdir(parents=True, exist_ok=True)

        book_file = Path(opening_book_path) if opening_book_path else (self.books_dir / "titans.bin")
        tactics_file = Path(tactics_path) if tactics_path else (self.tactics_dir / "tactics.epd")
        syzygy_dir_path = Path(syzygy_path) if syzygy_path else self.syzygy_dir

        self.opening_book = OpeningBook(book_path=book_file)
        self.tactics_db = TacticsDatabase(epd_path=tactics_file)
        self.endgame_db = EndgameDatabase(syzygy_path=syzygy_dir_path)
        self.history_store = HistoryStore(
            root=self.games_dir,
            opening_book=self.opening_book,
            tactics_db=self.tactics_db,
            endgame_db=self.endgame_db,
        )

    def query(self, category: str = "history", **kwargs) -> Dict[str, Any]:
        """统一对外查询"""
        return self.history_store.query_database(category=category, **kwargs)

    def close(self):
        """释放底层数据库连接与资源"""
        if self.endgame_db:
            self.endgame_db.close()
