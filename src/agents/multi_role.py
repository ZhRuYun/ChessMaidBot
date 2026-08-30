"""
多角色 Agent 编排体系 (模块5 - Agent 扩展)
- RefereeAgent (裁判员/规则评估)
- CoachAgent (教练/纯净棋理分析)
- MaidPersonaAgent (女仆人格润色与陪伴)
- MultiRoleCoordinator (多角色协同调度器)
"""
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable

from .base import ChessAgent, AgentRequest, PositionSnapshot


@dataclass
class TacticalAnalysis:
    score_cp: Optional[int]
    tactical_theme: str
    suggested_moves: list[dict]
    blunder_warning: Optional[str]


class CoachRole:
    """专注客观棋理与战术计算的教练分析器"""

    @staticmethod
    def build_analysis_prompt(snapshot: PositionSnapshot) -> str:
        return (
            f"你是一位特级大师级国际象棋教练。\n"
            f"请对当前局面 FEN: `{snapshot.fen}` 进行纯客观、严谨的棋理与战术评估。\n"
            f"要求：\n"
            f"1. 评估子力协调、兵形、王安全与关键格控制。\n"
            f"2. 输出 3 个最佳候选走法及战术后续。\n"
            f"3. 保持客观、专业，禁止输出寒暄套话。"
        )


class MaidPersonaRole:
    """女仆人格润色器：将严谨的分析包装为主仆陪伴风格"""

    @staticmethod
    def wrap_content(maid_persona: str, coach_analysis: str) -> str:
        # 在不需要额外网络请求时做本地人格组装，或通过单次 Prompt 融合
        return coach_analysis
