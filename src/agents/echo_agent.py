"""
本地回声代理 - ChessAgent 的占位实现
在接入真实 LLM 前提供固定的局面解读回复, 保证交互链路可用
"""
from typing import Optional

from .base import AgentRequest, ChessAgent


class EchoAgent(ChessAgent):
    name = "echo"

    def __init__(self, persona_prompt: Optional[str] = None):
        self.persona_prompt = persona_prompt or ""

    def reply(self, request: AgentRequest, on_chunk=None) -> str:
        snap = request.snapshot
        if snap.game_over_reason:
            res = (
                f"主人，这一局已经结束了呢～ ({snap.game_over_reason})<br>"
                f"最终局面 FEN: `{snap.fen}`"
            )
        else:
            res = (
                f"主人，我已经收到您的提问：*“{request.user_message}”*。<br>"
                f"【当前局面】: 轮到 **{snap.turn}** 行动，共有 **{snap.legal_move_count}** 种合法走法。<br>"
                f"FEN: `{snap.fen}`"
            )
        if on_chunk:
            on_chunk(res)
        return res
