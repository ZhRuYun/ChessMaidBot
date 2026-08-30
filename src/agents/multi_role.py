"""
多角色 Agent 编排体系 (模块5 - Agent 扩展)
两段式流水线 (由 LLMAgent._reply_two_stage 调用):
  1. CoachRole: 特级大师教练, JSON 结构化客观棋理分析 (低温 + json_object)
  2. MaidPersonaRole: 女仆人格润色, 保留棋理结论不改事实
  MultiRoleCoordinator: 组装两阶段消息序列; MaidPersonaRole.wrap_content 为
  第二阶段不可用时的本地降级包装 (零额外网络请求)。
Prompt 模板统一来自 prompt_registry (版本化)。
"""
from typing import List, Tuple

from .base import PositionSnapshot
from . import prompt_registry

# 教练阶段 JSON Schema (以文本形式写入 Prompt; 端点支持 json_object 时生效)
COACH_SCHEMA = (
    '{"evaluation": "一句话局面评估(含优劣势)", '
    '"threats": ["当前关键威胁或计划"], '
    '"candidate_moves": [{"san": "合法着法SAN", "idea": "核心意图与后续"}]}'
)


class CoachRole:
    """专注客观棋理与战术计算的教练分析器 (第一阶段)"""

    @staticmethod
    def build_coach_messages(fen: str) -> Tuple[List[dict], str]:
        """返回 (messages, schema_text); messages 直接用于 /chat/completions"""
        messages = [
            {"role": "system", "content": "你是特级大师级国际象棋教练。输出必须且仅包含 JSON 格式对象。"},
            {"role": "user", "content": prompt_registry.render("coach_analysis", fen=fen, schema=COACH_SCHEMA)},
        ]
        return messages, COACH_SCHEMA


class MaidPersonaRole:
    """女仆人格润色器：将严谨的教练分析包装为主仆陪伴风格 (第二阶段)"""

    @staticmethod
    def wrap_content(maid_persona: str, coach_analysis: str) -> str:
        """本地降级包装: 第二阶段网络调用不可用时, 以极简方式融合人设"""
        persona_brief = (maid_persona or "").strip().split("。")[0]
        return f"{persona_brief}。以下为主人的对局分析要点：\n{coach_analysis}"


class MultiRoleCoordinator:
    """多角色协同调度器: 组装 Coach -> Maid 两段式消息序列"""

    @staticmethod
    def coach_messages(fen: str) -> Tuple[List[dict], str]:
        return CoachRole.build_coach_messages(fen)

    @staticmethod
    def maid_messages(persona_prompt: str, coach_json: str, snapshot: PositionSnapshot) -> List[dict]:
        """第二阶段: 以人设 + 教练 JSON 数据组装改写消息 (注入防护由模板 trusted 标记承担)"""
        system = (
            f"{persona_prompt}\n\n"
            f"{prompt_registry.render('system_guard')}\n\n"
            "【当前棋盘基础快照】\n"
            f"- FEN: `{snapshot.fen}`\n"
            f"- 终局原因: {snapshot.game_over_reason or '对弈中'}"
        )
        user = prompt_registry.render("maid_rewrite", coach_json=coach_json)
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    @staticmethod
    def local_compose(persona_prompt: str, coach_analysis: str) -> str:
        """全本地降级组合 (零网络): 两阶段均不可用时使用"""
        return MaidPersonaRole.wrap_content(persona_prompt, coach_analysis)
