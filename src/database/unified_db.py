"""
统一数据库管理器 (模块6 - Unified Database Manager)
将历史棋局库与开局库聚合在单一入口下，统一管理 data/ 大目录中的子库
"""
from pathlib import Path
from typing import Optional, Dict, Any, Union

from ..config import DATA_DIR
from .history_store import HistoryStore
from .opening_book import OpeningBook


class UnifiedDatabase:
    """统一数据库大目录管理器"""

    def __init__(
        self,
        base_data_dir: Optional[Union[str, Path]] = None,
        opening_book_path: Optional[Union[str, Path]] = None,
        json_path: Optional[Union[str, Path]] = None,
    ):
        self.data_dir = Path(base_data_dir) if base_data_dir else DATA_DIR
        self.games_dir = self.data_dir / "games"
        self.books_dir = self.data_dir / "books"

        # 确保全部子目录存在
        for d in (self.data_dir, self.games_dir, self.books_dir):
            d.mkdir(parents=True, exist_ok=True)

        book_file = Path(opening_book_path) if opening_book_path else (self.books_dir / "titans.bin")
        openings_json_file = Path(json_path) if json_path else (self.books_dir / "openings.json")

        self.opening_book = OpeningBook(book_path=book_file, json_path=openings_json_file)
        self.history_store = HistoryStore(
            root=self.games_dir,
            opening_book=self.opening_book,
        )

    def get_status(self) -> Dict[str, Any]:
        """获取子数据库的就绪与文件状态摘要"""
        return {
            "data_dir": str(self.data_dir),
            "games_count": len(self.history_store.list_games(filter_useless=False)),
            "useful_games_count": len(self.history_store.list_games(filter_useless=True)),
            "opening_book": {
                "has_polyglot": self.opening_book.has_polyglot_book(),
                "json_entries": len(self.opening_book._custom_patterns),
            },
        }

    def query(self, category: str = "history", **kwargs) -> Dict[str, Any]:
        """统一对外查询"""
        return self.history_store.query_database(category=category, **kwargs)

    def close(self):
        """释放底层数据库连接与资源"""
        pass
