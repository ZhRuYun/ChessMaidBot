"""
教学触发器配置 (模块2 - 调度层)
决定 LLM 教学哪些内容: 1 个总开关 + 4 个细分开关
"""
from dataclasses import dataclass


@dataclass
class TeachingTriggers:
    master_enabled: bool = True
    eval_current_position: bool = True
    suggest_moves: bool = True
    eval_history_moves: bool = True
    game_over_summary: bool = True

    @property
    def active(self) -> bool:
        """总开关开启且至少一个细分开关开启"""
        return self.master_enabled and (
            self.eval_current_position
            or self.suggest_moves
            or self.eval_history_moves
            or self.game_over_summary
        )
