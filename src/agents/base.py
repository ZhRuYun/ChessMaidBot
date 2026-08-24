"""
Agent 接口与标准请求格式 (模块5)
所有 LLM/引擎陪练实现均遵循 ChessAgent 接口;
AgentRequest 即发给 LLM 的"标准格式"打包: 用户消息 + 人设 + 局面快照 + 可选数据库/引擎上下文方法库支持
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable


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
class AgentTools:
    """为 LLM 提供的外部上下文读取方法库接口 (模块5要求的方法1~4)
    
    1. 允许 LLM 自行决定是否读取数据库
    2. 如果允许读取数据库，读取数据库的哪一部分内容 (如: history, opening, tactics, endgame)
    3. 允许 LLM 自行决定是否读取 Stockfish 引擎状态
    4. 如果允许读取引擎状态，读取哪一部分内容 (如: best_move, eval_multipv)
    5. 联网搜索工具 (web_search)
    """
    read_database: Optional[Callable[[str, Dict[str, Any]], Any]] = None
    read_engine_state: Optional[Callable[[str, Dict[str, Any]], Any]] = None
    web_search: Optional[Callable[[str], str]] = None


@dataclass
class AgentRequest:
    """发给大模型的标准请求体"""
    user_message: str
    persona_prompt: str
    snapshot: PositionSnapshot
    dialog_history: List[dict] = field(default_factory=list)
    tools: Optional[AgentTools] = None
    game_mode: Optional[str] = None


class ChessAgent(ABC):
    """LLM 教学代理抽象基类

    面向 LLM 对话的抽象与标准化上下文打包。
    子类实现 reply() 生成 Markdown 格式回复，支持自主决定调用 tools 提供的数据库/引擎工具。
    """

    name: str = "agent"

    @abstractmethod
    def reply(self, request: AgentRequest) -> str:
        """根据标准请求生成回复 (Markdown 文本)"""
        raise NotImplementedError
