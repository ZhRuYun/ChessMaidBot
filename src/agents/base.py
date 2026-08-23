"""
Agent 接口与标准请求格式 (模块5)
所有 LLM/引擎陪练实现均遵循 ChessAgent 接口;
AgentRequest 即发给 LLM 的"标准格式"打包: 用户消息 + 人设 + 局面快照
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PositionSnapshot:
    """当前局面快照 (纯数据, 便于序列化给任意 LLM 后端)"""
    fen: str
    pgn: str
    turn: str
    legal_move_count: int
    in_check: bool
    last_move_san: Optional[str] = None
    game_over_reason: str = ""


@dataclass
class AgentRequest:
    user_message: str
    persona_prompt: str
    snapshot: PositionSnapshot
    dialog_history: List[dict] = field(default_factory=list)


class ChessAgent(ABC):
    """LLM 教学代理抽象基类

    未来接入真实 LLM / 数据库读取 / 引擎状态读取时,
    在子类中实现 reply() 即可, 上层调度与 GUI 无需改动
    """

    name: str = "agent"

    @abstractmethod
    def reply(self, request: AgentRequest) -> str:
        """根据标准请求生成回复 (Markdown 文本)"""
        raise NotImplementedError
