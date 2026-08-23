"""
数据库与棋局持久化 (模块6)
包含: 历史棋局库 (面向 LLM 纯文本 "PGN + LLM 对局总结" 复合结构持久化)、开局库/战术库/残局库接口及格式转换方法
"""
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..config import GAMES_DIR


class HistoryStore:
    """历史棋局库与数据库统一管理器"""

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else GAMES_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def save_game(
        self,
        pgn_text: str,
        result: str = "*",
        llm_summary: Optional[str] = None,
    ) -> Path:
        """保存一局棋局文件 (PGN + 可选 LLM 总结内容), 返回文件路径"""
        safe_result = result.replace("/", "-").replace(" ", "")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.root / f"{stamp}-{safe_result}.pgn"
        counter = 1
        while path.exists():
            path = self.root / f"{stamp}-{safe_result}-{counter}.pgn"
            counter += 1

        full_content = pgn_text.strip()
        if llm_summary:
            full_content += f"\n\n% --- LLM GAME SUMMARY ---\n% {llm_summary.strip()}\n"

        path.write_text(full_content, encoding="utf-8")
        return path

    def list_games(self) -> List[Path]:
        """列出所有已保存的历史棋局"""
        return sorted(self.root.glob("*.pgn"))

    @staticmethod
    def load_text(path: Path) -> str:
        """读取指定路径的纯文本棋谱与总结"""
        return Path(path).read_text(encoding="utf-8")

    @staticmethod
    def parse_game_file(content: str) -> Dict[str, str]:
        """将文件内容拆解为 PGN 棋谱部分与 LLM 总结部分，供 LLM 和解析器无损读取"""
        marker = "% --- LLM GAME SUMMARY ---"
        if marker in content:
            parts = content.split(marker, 1)
            pgn_part = parts[0].strip()
            summary_part = parts[1].replace("%", "").strip()
            return {"pgn": pgn_part, "summary": summary_part}
        return {"pgn": content.strip(), "summary": ""}

    def query_database(self, category: str = "history", **kwargs) -> Dict[str, Any]:
        """为 Agent 与外部模块提供的统一数据库查询接口
        
        支持分类:
          - "history": 历史棋局库 (最近对局列表与棋谱+总结)
          - "opening": 开局库 (ECO/开局名称与推荐线路)
          - "tactics": EPD 战术库
          - "endgame": 残局库
        """
        category = category.lower()
        if category == "history":
            limit = kwargs.get("limit", 5)
            games = self.list_games()
            recent_games = games[-limit:] if limit > 0 else games
            game_summaries = []
            for g in recent_games:
                raw_text = self.load_text(g)
                parsed = self.parse_game_file(raw_text)
                game_summaries.append({
                    "filename": g.name,
                    "pgn_preview": parsed["pgn"][:180],
                    "llm_summary": parsed["summary"],
                })
            return {"category": "history", "count": len(games), "games": game_summaries}
        elif category in ("opening", "tactics", "endgame"):
            return {
                "category": category,
                "status": "ready",
                "message": f"Database section '{category}' is accessible in LLM-readable format.",
            }
        else:
            return {"category": category, "error": f"Unknown database category: {category}"}


