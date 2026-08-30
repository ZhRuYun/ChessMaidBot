"""
数据库与棋局持久化 (模块6)
包含: 历史棋局库 (面向 LLM 纯文本 "PGN + LLM 对局总结" 复合结构持久化)、开局库接口及格式转换方法
"""
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..config import GAMES_DIR
from .opening_book import OpeningBook


class HistoryStore:
    """历史棋局库与数据库统一管理器 (统筹历史对局与开局库)"""

    def __init__(
        self,
        root: Optional[Path] = None,
        opening_book: Optional[OpeningBook] = None,
    ):
        self.root = Path(root) if root else GAMES_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        self.opening_book = opening_book or OpeningBook()

    def save_game(
        self,
        pgn_text: str,
        result: str = "*",
        llm_summary: Optional[str] = None,
    ) -> Optional[Path]:
        """保存一局棋局文件 (标准 PGN 格式并在尾部包含可选 LLM 总结), 仅在正常完赛时存盘, 返回文件路径或 None"""
        if not self.is_useful_game(pgn_text, result=result):
            return None

        # 清洗文件名非法字符 (Windows: \ / : * ? " < > |), 避免 OSError
        illegal = '<>:"/\\|?* '
        safe_result = result
        for ch in illegal:
            safe_result = safe_result.replace(ch, "-")
        safe_result = safe_result.strip("-") or "finished"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.root / f"{stamp}-{safe_result}.pgn"
        counter = 1
        while path.exists():
            path = self.root / f"{stamp}-{safe_result}-{counter}.pgn"
            counter += 1

        full_content = pgn_text.strip()
        if llm_summary and llm_summary.strip():
            # 标准简洁结构：使用标准 PGN 注释段
            full_content += f"\n\n% --- LLM GAME SUMMARY ---\n% {llm_summary.strip()}\n"

        path.write_text(full_content + "\n", encoding="utf-8")
        return path

    @staticmethod
    def is_useful_game(pgn_text: str, result: Optional[str] = None) -> bool:
        """
        判断棋局是否符合储存标准:
        只有玩家正常游玩，以将死对手、被对手将死、认输、同意求和等正常结束游戏的棋局才会存入历史游戏库。
        排除 0 步/未开局即退、进行中未完赛 ("*") 的对局。
        """
        if not pgn_text or not pgn_text.strip():
            return False

        # 检查终局结果是否有效 (1-0, 0-1, 1/2-1/2)
        valid_results = {"1-0", "0-1", "1/2-1/2"}
        if result is not None and result not in valid_results:
            return False

        # 提取走法主体部分（去掉 [Header] 行和注释）
        lines = [line.strip() for line in pgn_text.splitlines() if line.strip() and not line.startswith("[") and not line.startswith("%")]
        moves_body = " ".join(lines).strip()

        # 如果没有着法或仅为孤立结果标识
        if not moves_body or moves_body in valid_results or moves_body == "*":
            return False

        # 提取结果标记（若未直接传入 result 参数）
        if result is None:
            has_valid_term = any(moves_body.endswith(r) for r in valid_results)
            # 或者头信息中包含有效结果
            if not has_valid_term:
                header_res = False
                for line in pgn_text.splitlines():
                    if line.startswith('[Result "') and any(r in line for r in valid_results):
                        header_res = True
                        break
                if not header_res:
                    return False

        # 必须至少包含第一步有效着法（例如 "1." 或 "1..."）
        return "1." in moves_body

    def list_games(self, filter_useless: bool = True) -> List[Path]:
        """列出所有已保存的历史棋局，默认自动过滤无效棋局"""
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
          - "history": 历史对局查询与归档检索 (最近对局列表与棋谱+总结;
            可选 query 关键词, 在总结/棋谱上做轻量相关性检索, RAG-lite)
          - "opening": 开局库查询候选走法及权重 (ECO/开局名称与推荐候选着法及权重)
        """
        category = category.lower()
        if category == "history":
            limit = kwargs.get("limit", 5)
            filter_useless = kwargs.get("filter_useless", True)
            query = (kwargs.get("query") or "").strip()
            games = self.list_games(filter_useless=filter_useless)
            entries = []
            for g in games:
                try:
                    raw_text = self.load_text(g)
                except Exception:
                    continue
                parsed = self.parse_game_file(raw_text)
                entries.append({
                    "filename": g.name,
                    "pgn_preview": parsed["pgn"][:180],
                    "llm_summary": parsed["summary"],
                    "_text": (parsed["summary"] + "\n" + parsed["pgn"][:400]).lower(),
                })

            if query:
                # 增强轻量 RAG: 支持多关键词与 FEN 结构片段匹配评分
                terms = [t for t in query.lower().replace(",", " ").replace(";", " ").split() if len(t) >= 2]
                scored = []
                for e in entries:
                    score = 0
                    for t in terms:
                        if t in e["_text"]:
                            # 总结匹配权重大于原始PGN预览
                            score += 3 if t in e.get("llm_summary", "").lower() else 1
                    if score > 0:
                        scored.append((score, e))
                scored.sort(key=lambda x: (-x[0], x[1]["filename"]))
                entries = [e for _, e in scored]
                relevance = "keyword"
            else:
                entries = entries[-limit:] if limit > 0 else entries
                relevance = "recent"

            for e in entries:
                e.pop("_text", None)
            recent_games = entries[:limit] if limit > 0 else entries
            return {
                "category": "history",
                "count": len(games),
                "relevance": relevance,
                "games": recent_games,
            }
        elif category == "opening":
            fen = kwargs.get("fen", "")
            limit = kwargs.get("limit", 5)
            if fen:
                res = self.opening_book.query_opening(fen, limit=limit)
                return {"category": "opening", "status": "ready", **res}
            return {
                "category": "opening",
                "status": "ready",
                "has_polyglot_book": self.opening_book.has_polyglot_book(),
                "message": "Opening book is ready. Provide 'fen' in params to query lines and ECO names.",
            }
        else:
            return {"category": category, "error": f"Unknown database category: {category}. Only 'opening' and 'history' are supported."}


