"""
教学提示词构建器 (模块5 - Agent 辅助)
根据当前棋盘现状信息 (FEN, 行动方, 最近走法) 和 4 个教学子开关状态生成定制 Prompt。

Token 成本说明 (单源化):
  完整 PGN 统一由 LLMAgent._build_context_block 在 System 上下文块中提供 (尾部窗口截断),
  本构建器不再内嵌完整 PGN, 避免同一请求重复携带双份棋谱。
  安全与格式规范页脚统一取自 prompt_registry (版本化)。
"""
from typing import Optional
from .base import PositionSnapshot
from . import prompt_registry
from ..controller.teaching_triggers import TeachingTriggers


class PromptBuilder:
    """构建与棋盘现状及 4 个子开关严格联动的定制教学 Prompt"""

    @staticmethod
    def build_custom_prompt(
        snapshot: PositionSnapshot,
        triggers: TeachingTriggers,
        is_auto_move: bool = False,
        extra_note: Optional[str] = None,
        game_mode_name: Optional[str] = None,
    ) -> str:
        """
        根据快照与开关状态组装定制 Prompt。
        若所有子开关均关闭，但触发了提问，则默认进行全局局面解读。
        """
        sections = []

        if triggers.eval_current_position:
            sections.append(
                "1. **当下局面评估**：精准剖析子力平衡、兵形结构、王的安全度与关键格控制，明确优劣势对比。"
            )

        if not snapshot.game_over_reason:
            sections.append(
                "2. **建议着法**：必须提供当前行动方最值得考虑的 3 个合法候选着法；每个候选只用一行说明核心意图、主要后续与必要防范。"
            )

        if triggers.eval_history_moves:
            if snapshot.last_move_san:
                sections.append(
                    f"3. **历史走法评估 (失误预警)**：重点点评最近一手 `{snapshot.last_move_san}`，指出是否存在战术漏洞、疑问手或亮眼战术构思。"
                )
            else:
                sections.append(
                    "3. **历史走法评估 (失误预警)**：评估当前开局走法是否符合出子原则与中心争夺。"
                )

        if triggers.game_over_summary and snapshot.game_over_reason:
            sections.append(
                f"4. **棋局结束总结 (赛后复盘)**：对局已终局（{snapshot.game_over_reason}），请进行全面战术复盘，总结胜负手与关键转折局面。"
            )

        if not sections:
            # 当所有子开关都未勾选时的兜底通用分析要求
            sections.append("请结合当前棋盘局势，为主人提供精辟的棋理剖析与关键战略建议。")

        requirements_text = "\n".join(sections)

        trigger_source = "【自动教学触发】" if is_auto_move else "【主动询问女仆教学指导】"
        if snapshot.player_side == "black":
            player_side_str = "执黑方（先手白方为对手/引擎，后手黑方为你侍奉的主人）"
        elif snapshot.player_side == "white":
            player_side_str = "执白方（先手白方为你侍奉的主人，后手黑方为对手/引擎）"
        else:
            player_side_str = "执白方"
        mode_text = f"\n- 当前游戏模式: {game_mode_name}" if game_mode_name else ""
        note_text = f"\n补充说明: {extra_note}" if extra_note else ""

        prompt = f"""{trigger_source}
请根据以下国际象棋对局信息提供指导：

<!-- BEGIN_TRUSTED_CHESS_DATA -->
【棋盘现状】{mode_text}
- 玩家执棋方 (你的主人): {player_side_str}
- 局势状态: {"已终局 (" + snapshot.game_over_reason + ")" if snapshot.game_over_reason else "对弈中"}
- 当前行动方: {snapshot.turn}
- 最近一步: {snapshot.last_move_san or "开局初始"}
- 当前 FEN 码: `{snapshot.fen}`
(完整对局 PGN 记谱以系统上下文块提供的尾部窗口为准，此处不重复内嵌)
<!-- END_TRUSTED_CHESS_DATA -->

【分析解答要点】：
{requirements_text}{note_text}

{prompt_registry.render("teaching_rules")}"""
        return prompt.strip()
