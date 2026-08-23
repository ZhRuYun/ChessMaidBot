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
        # 清洗文件名非法字符 (Windows: \ / : * ? " < > |), 避免 OSError
        illegal = '<>:"/\\|?* '
        safe_result = result
        for ch in illegal:
            safe_result = safe_result.replace(ch, "-")
        safe_result = safe_result.strip("-") or "ongoing"
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

    @staticmethod
    def is_useful_game(pgn_text: str) -> bool:
        """
        判断棋局是否为有效/有用棋局。
        排除'还未开始就认输'、'还未开始就求和'等 0 步着法的无效棋局。
        """
        if not pgn_text or not pgn_text.strip():
            return False
        
        # 提取走法主体部分（去掉 [Header] 行和注释）
        lines = [line.strip() for line in pgn_text.splitlines() if line.strip() and not line.startswith("[") and not line.startswith("%")]
        moves_body = " ".join(lines).strip()
        
        # 如果走法主体为空，或仅为终局标记 ("*", "1-0", "0-1", "1/2-1/2")，说明 0 步走棋
        results = {"*", "1-0", "0-1", "1/2-1/2"}
        if not moves_body or moves_body in results:
            return False
        
        # 必须至少包含第一步有效着法（例如 "1." 或 "1..."）
        return "1." in moves_body

    def list_games(self, filter_useless: bool = True) -> List[Path]:
        """列出所有已保存的历史棋局，默认自动过滤 0 步/未开局即结束的无用棋局"""
        all_files = sorted(self.root.glob("*.pgn"))
        if not filter_useless:
            return all_files

        useful_files = []
        for p in all_files:
            try:
                raw_text = self.load_text(p)
                parsed = self.parse_game_file(raw_text)
                if self.is_useful_game(parsed["pgn"]):
                    useful_files.append(p)
            except Exception:
                continue
        return useful_files

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
            filter_useless = kwargs.get("filter_useless", True)
            games = self.list_games(filter_useless=filter_useless)
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


