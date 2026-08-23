"""
对弈模式管理器 (模块2 - 调度层)
当前实现本地双人; 人机 (Stockfish) 与女仆 (LLM) 模式预留接入点
"""
from enum import Enum


class GameMode(Enum):
    LOCAL_PVP = "local_pvp"
    VS_ENGINE = "vs_engine"
    VS_MAID_LLM = "vs_maid_llm"


MODE_LABELS = {
    GameMode.LOCAL_PVP: "本地双人对战 (Local PvP)",
    GameMode.VS_ENGINE: "人机对弈 (vs Stockfish)",
    GameMode.VS_MAID_LLM: "女仆陪练 (vs Maid LLM)",
}

STOCKFISH_SKILL_RANGE = (0, 20)


class GameModeManager:
    """维护当前对弈模式与引擎参数"""

    def __init__(self):
        self.mode = GameMode.LOCAL_PVP
        self.engine_skill = 10

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

    def player_names(self):
        """按模式返回 (白方, 黑方) 对局头名称"""
        if self.mode == GameMode.VS_ENGINE:
            return "Player", f"Stockfish (Lv.{self.engine_skill})"
        if self.mode == GameMode.VS_MAID_LLM:
            return "Player", "ChessMaid"
        return "Player 1", "Player 2"
