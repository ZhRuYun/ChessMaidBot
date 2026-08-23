"""
教学提示词构建器 (模块5 - Agent 辅助)
根据当前棋盘现状信息 (PGN, FEN, 行动方, 最近走法) 和 4 个教学子开关状态生成定制 Prompt
"""
from typing import Optional
from .base import PositionSnapshot
from ..controller.teaching_triggers import TeachingTriggers


class PromptBuilder:
    """构建与棋盘现状及 4 个子开关严格联动的定制教学 Prompt"""

    @staticmethod
    def build_custom_prompt(
        snapshot: PositionSnapshot,
        triggers: TeachingTriggers,
        is_auto_move: bool = False,
        extra_note: Optional[str] = None
    ) -> str:
        """
        根据快照与开关状态组装定制 Prompt。
        若所有子开关均关闭，但触发了提问，则默认进行全局局面解读。
        """
        sections = []

        if triggers.eval_current_position:
            sections.append(
                "1. **当下局面评估**：分析当前双方子力平衡、王的安全度、中心控制及关键格子争夺情况，评估优劣势。"
            )

        if triggers.suggest_moves and not snapshot.game_over_reason:
            sections.append(
                "2. **建议着法推荐**：为当前行动方提供 1~3 步高质量候选着法思路，解释每步的战术意图与后续计划。"
            )

        if triggers.eval_history_moves:
            if snapshot.last_move_san:
                sections.append(
                    f"3. **历史走法评估 (失误预警)**：重点点评刚刚下出的 `{snapshot.last_move_san}`，指出是否存在战术漏洞、疑问手或绝妙构思。"
                )
            else:
                sections.append(
                    "3. **历史走法评估 (失误预警)**：评估历史开局走法是否存在潜在隐患或失误。"
                )

        if triggers.game_over_summary and snapshot.game_over_reason:
            sections.append(
                f"4. **棋局结束总结 (赛后复盘)**：对局已结束（{snapshot.game_over_reason}），请对整盘棋进行全面复盘点评，总结双方关键转折点。"
            )

        if not sections:
            # 当所有子开关都未勾选时的兜底通用分析要求
            sections.append("请结合当前棋盘现状，为主人进行通用的棋局状态讲解与战略建议。")

        requirements_text = "\n".join(sections)

        trigger_source = "【玩家落子自动教学触发】" if is_auto_move else "【主动询问女仆教学指导】"
        note_text = f"\n补充说明: {extra_note}" if extra_note else ""

        prompt = f"""{trigger_source}
请根据以下国际象棋对局信息提供指导：

【棋盘现状】
- 局势状态: {"已终局 (" + snapshot.game_over_reason + ")" if snapshot.game_over_reason else "对弈中"}
- 当前行动方: {snapshot.turn}
- 最近一步: {snapshot.last_move_san or "开局初始"}
- 当前 FEN 码: `{snapshot.fen}`
- 完整对局 PGN:
```pgn
{snapshot.pgn.strip()}
```

【请针对以下开启的要点进行分析解答】：
{requirements_text}{note_text}

请以温柔细致、专业且富有启发性的 AI 棋艺女仆身份，使用整洁美观的 Markdown 格式为主人呈现解答。"""
        return prompt.strip()
