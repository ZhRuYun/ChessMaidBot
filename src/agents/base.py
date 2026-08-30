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
    player_side: Optional[str] = None


@dataclass
class AgentTools:
    """为 LLM 提供的外部上下文与工具接口:
    
    1. query_opening: 开局库查询候选走法及权重 (以 FEN 查开局名称/推荐走法)
    2. query_history: 历史对局查询与归档检索 (获取玩家已归档历史对局及总结)
    3. read_database: 统一数据库读取代理 (category="opening" 或 "history")
    4. read_engine_state: 引擎状态读取 (best_move, analyse, eval)
    5. web_search: 联网搜索工具 (国际象棋术语、棋理与知识检索)
    6. request_undo: 与LLM对弈模式下，LLM判断局势不利时向玩家发送悔棋请求
    """
    query_opening: Optional[Callable[[Optional[str], int], Dict[str, Any]]] = None
    query_history: Optional[Callable[[int, bool], Dict[str, Any]]] = None
    read_database: Optional[Callable[[str, Dict[str, Any]], Any]] = None
    read_engine_state: Optional[Callable[[str, Dict[str, Any]], Any]] = None
    web_search: Optional[Callable[[str], str]] = None
    request_undo: Optional[Callable[[str], bool]] = None


@dataclass
class AgentRequest:
    """发给大模型的标准请求体"""
    user_message: str
    persona_prompt: str
    snapshot: PositionSnapshot
    dialog_history: List[dict] = field(default_factory=list)
    tools: Optional[AgentTools] = None
    game_mode: Optional[str] = None
    # False 表示 user_message 为用户自由输入原文, 发送时需包裹 <untrusted_user_input> 防注入标记
    trust_user_message: bool = True
    # 玩家长期画像摘要 (若注入)
    player_profile_summary: Optional[str] = None


class ChessAgent(ABC):
    """LLM 教学代理抽象基类

    面向 LLM 对话的抽象与标准化上下文打包。
    子类实现 reply() 生成 Markdown 格式回复，支持自主决定调用 tools 提供的数据库/引擎工具。
    """

    name: str = "agent"

    @abstractmethod
    def reply(self, request: AgentRequest, on_chunk: Optional[Callable[[str], None]] = None) -> str:
        """根据标准请求生成回复 (Markdown 文本), 支持可选的 on_chunk 流式回调"""
        raise NotImplementedError
