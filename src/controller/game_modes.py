"""
对弈模式管理器 (模块2 - 调度层)
维护当前对弈模式（本地双人、人机 Stockfish 对弈、女仆 LLM 陪练）与引擎强度（Skill / 目标 Elo）
"""
from enum import Enum
from typing import Optional

from ..config import (
    STOCKFISH_DEFAULT_SKILL,
    STOCKFISH_DEFAULT_ELO,
    STOCKFISH_MIN_ELO,
    STOCKFISH_MAX_ELO,
)


class GameMode(Enum):
    LOCAL_PVP = "local_pvp"
    VS_ENGINE = "vs_engine"
    VS_MAID_LLM = "vs_maid_llm"
    ONLINE_PVP = "online_pvp"


MODE_LABELS = {
    GameMode.LOCAL_PVP: "扮演双方棋手 (Play Both Sides)",
    GameMode.VS_ENGINE: "人机对弈 (vs Stockfish)",
    GameMode.VS_MAID_LLM: "女仆陪练 (vs Maid LLM)",
    GameMode.ONLINE_PVP: "网络双人对战 (Online PvP)",
}

STOCKFISH_SKILL_RANGE = (0, 20)


class GameModeManager:
    """维护当前对弈模式与引擎参数"""

    def __init__(self):
        self.mode = GameMode.LOCAL_PVP
        self.engine_skill = STOCKFISH_DEFAULT_SKILL
        self.target_elo: Optional[int] = STOCKFISH_DEFAULT_ELO
        self.use_elo: bool = True  # 默认启用目标 Elo 控制
        self.player_side = "white"  # "white" 或 "black" (在 VS_ENGINE / VS_MAID_LLM / ONLINE_PVP 下适用)

    def set_mode(self, mode: GameMode):
        self.mode = mode

    def set_mode_by_label(self, label: str) -> GameMode:
        for mode, mode_label in MODE_LABELS.items():
            if mode_label == label:
                self.mode = mode
                return mode
        return self.mode

    def set_engine_skill(self, skill: int):
        lo, hi = STOCKFISH_SKILL_RANGE
        self.engine_skill = max(lo, min(hi, skill))
        self.use_elo = False

    def set_target_elo(self, elo: int):
        self.target_elo = max(STOCKFISH_MIN_ELO, min(STOCKFISH_MAX_ELO, elo))
        self.use_elo = True

    def set_elo_preset(self, preset_name: str) -> Optional[int]:
        presets = {
            "新手": 500,
            "业余": 1000,
            "职业": 1500,
            "大师": 2000,
            "特级大师": 2500,
        }
        if preset_name in presets:
            elo = presets[preset_name]
            self.set_target_elo(elo)
            return elo
        return None

    def player_names(self):
        """按模式返回 (白方, 黑方) 对局头名称"""
        if self.mode == GameMode.VS_ENGINE:
            desc = f"Elo {self.target_elo}" if self.use_elo and self.target_elo else f"Lv.{self.engine_skill}"
            if self.player_side == "black":
                return f"Stockfish ({desc})", "Player"
            return "Player", f"Stockfish ({desc})"
        if self.mode == GameMode.VS_MAID_LLM:
            if self.player_side == "black":
                return "ChessMaid", "Player"
            return "Player", "ChessMaid"
        if self.mode == GameMode.ONLINE_PVP:
            return "Online White", "Online Black"
        return "Player 1", "Player 2"

