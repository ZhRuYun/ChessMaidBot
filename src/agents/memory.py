"""
长短期双层记忆系统 (模块5 - Agent 扩展)
- ShortTermMemory: 对局工作记忆与滑动窗口对话管理
- LongTermProfile: 玩家战术偏好、常用开局、历史失误类型分析持久化
"""
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..config import DATA_DIR


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
    frequent_blunders: Dict[str, int] = field(default_factory=dict)
    playstyle_tag: str = "平衡型"

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
            frequent_blunders=data.get("frequent_blunders", {}),
            playstyle_tag=data.get("playstyle_tag", "平衡型"),
        )


class LongTermMemory:
    """长期画像记忆：跨对局记录玩家风格与弱点"""

    def __init__(self, profile_path: Optional[Path] = None):
        self.profile_path = profile_path or (DATA_DIR / "player_profile.json")
        self.profile = self._load()

    def _load(self) -> PlayerProfile:
        if self.profile_path.exists():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    return PlayerProfile.from_dict(json.load(f))
            except Exception:
                return PlayerProfile()
        return PlayerProfile()

    def save(self):
        try:
            self.profile_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(self.profile.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

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

        if blunders:
            for b in blunders:
                self.profile.frequent_blunders[b] = self.profile.frequent_blunders.get(b, 0) + 1

        self._update_playstyle()
        self.save()

    def _update_playstyle(self):
        blunder_count = sum(self.profile.frequent_blunders.values())
        if self.profile.total_games >= 3:
            if blunder_count / max(1, self.profile.total_games) > 2.5:
                self.profile.playstyle_tag = "激进易漏防型"
            else:
                self.profile.playstyle_tag = "沉稳战术型"

    def get_summary_prompt(self) -> str:
        """生成供 LLM 注入的玩家长期画像上下文"""
        fav_ops = sorted(self.profile.favorite_openings.items(), key=lambda x: x[1], reverse=True)[:2]
        fav_ops_str = ", ".join([f"{k}({v}次)" for k, v in fav_ops]) if fav_ops else "暂无"
        return (
            f"【主人对弈画像档案】\n"
            f"- 总对局: {self.profile.total_games} 局 (胜: {self.profile.wins}, 负: {self.profile.losses}, 和: {self.profile.draws})\n"
            f"- 棋风标签: {self.profile.playstyle_tag}\n"
            f"- 偏好开局: {fav_ops_str}"
        )
