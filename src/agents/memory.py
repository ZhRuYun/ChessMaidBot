"""
长短期双层记忆系统 (模块5 - Agent 扩展)
- ShortTermMemory: 对局工作记忆与滑动窗口对话管理
- LongTermProfile: 玩家战术偏好、常用开局、历史失误类型分析持久化
"""
import json
import logging
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..config import DATA_DIR

logger = logging.getLogger("chessmaid.memory")


@dataclass
class DialogTurn:
    role: str
    content: str
    move_context: Optional[str] = None
    fen: Optional[str] = None


class ShortTermMemory:
    """短期工作记忆：维护当前局面的上下文窗口"""

    def __init__(self, max_turns: int = 12):
        self.max_turns = max_turns
        self.history: List[DialogTurn] = []

    def add_turn(self, role: str, content: str, move_context: Optional[str] = None, fen: Optional[str] = None):
        turn = DialogTurn(role=role, content=content, move_context=move_context, fen=fen)
        self.history.append(turn)
        if len(self.history) > self.max_turns:
            self.history = self.history[-self.max_turns:]

    def get_messages(self) -> List[Dict[str, str]]:
        return [{"role": t.role, "content": t.content} for t in self.history]

    def clear(self):
        self.history.clear()


@dataclass
class PlayerProfile:
    total_games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    favorite_openings: Dict[str, int] = field(default_factory=dict)
    weakness_notes: List[str] = field(default_factory=list)
    coach_advices: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerProfile":
        return cls(
            total_games=data.get("total_games", 0),
            wins=data.get("wins", 0),
            losses=data.get("losses", 0),
            draws=data.get("draws", 0),
            favorite_openings=data.get("favorite_openings", {}),
            weakness_notes=data.get("weakness_notes", []),
            coach_advices=data.get("coach_advices", []),
        )


class LongTermMemory:
    """长期基础档案：记录玩家战绩、常用开局与关键总结"""

    def __init__(self, profile_path: Optional[Path] = None):
        self.profile_path = profile_path or (DATA_DIR / "player_profile.json")
        self.profile = self._load()

    def _load(self) -> PlayerProfile:
        if self.profile_path.exists():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    return PlayerProfile.from_dict(json.load(f))
            except Exception as e:
                logger.warning("读取长期记忆画像失败，使用默认画像: %s", e)
                return PlayerProfile()
        return PlayerProfile()

    def save(self):
        try:
            self.profile_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.profile.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("长期画像持久化保存失败: %s", e, exc_info=True)

    def record_distilled_insight(self, weakness: Optional[str] = None, advice: Optional[str] = None):
        """记录从终局复盘中提取的弱点与建议"""
        if weakness and weakness.strip():
            w = weakness.strip()
            if w not in self.profile.weakness_notes:
                self.profile.weakness_notes.append(w)
                if len(self.profile.weakness_notes) > 3:
                    self.profile.weakness_notes = self.profile.weakness_notes[-3:]
        if advice and advice.strip():
            a = advice.strip()
            if a not in self.profile.coach_advices:
                self.profile.coach_advices.append(a)
                if len(self.profile.coach_advices) > 3:
                    self.profile.coach_advices = self.profile.coach_advices[-3:]
        self.save()

    def record_game_result(self, result: str, opening: Optional[str] = None, blunders: Optional[List[str]] = None):
        self.profile.total_games += 1
        if result == "1-0":
            self.profile.wins += 1
        elif result == "0-1":
            self.profile.losses += 1
        elif result == "1/2-1/2":
            self.profile.draws += 1

        if opening:
            self.profile.favorite_openings[opening] = self.profile.favorite_openings.get(opening, 0) + 1

        self.save()

    def get_summary_prompt(self) -> str:
        """生成供 LLM 注入的精简玩家档案 (若无记录则返回空，避免无意义注入)"""
        if self.profile.total_games == 0 and not self.profile.weakness_notes and not self.profile.coach_advices:
            return ""

        fav_ops = sorted(self.profile.favorite_openings.items(), key=lambda x: x[1], reverse=True)[:2]
        fav_ops_str = ", ".join([f"{k}({v}次)" for k, v in fav_ops]) if fav_ops else "暂无"
        lines = [
            "【主人历史战绩档案】",
            f"- 总对局: {self.profile.total_games} 局 (胜: {self.profile.wins}, 负: {self.profile.losses}, 和: {self.profile.draws})",
            f"- 偏好开局: {fav_ops_str}"
        ]
        if self.profile.weakness_notes:
            lines.append(f"- 历史失误提醒: {'; '.join(self.profile.weakness_notes[-2:])}")
        if self.profile.coach_advices:
            lines.append(f"- 历史复盘建议: {'; '.join(self.profile.coach_advices[-2:])}")
        return "\n".join(lines)
