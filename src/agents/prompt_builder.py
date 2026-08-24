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

        if triggers.suggest_moves and not snapshot.game_over_reason:
            sections.append(
                "2. **建议着法推荐**：为当前行动方提供 1~3 步高质量候选着法思路，剖析每步棋的战术意图、后续计划与防范要点。"
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

        trigger_source = "【玩家落子自动教学触发】" if is_auto_move else "【主动询问女仆教学指导】"
        mode_text = f"\n- 当前游戏模式: {game_mode_name}" if game_mode_name else ""
        note_text = f"\n补充说明: {extra_note}" if extra_note else ""

        prompt = f"""{trigger_source}
请根据以下国际象棋对局信息提供指导：

【棋盘现状】{mode_text}
- 局势状态: {"已终局 (" + snapshot.game_over_reason + ")" if snapshot.game_over_reason else "对弈中"}
- 当前行动方: {snapshot.turn}
- 最近一步: {snapshot.last_move_san or "开局初始"}
- 当前 FEN 码: `{snapshot.fen}`
- 完整对局 PGN:
```pgn
{snapshot.pgn.strip()}
```

【分析解答要点】：
{requirements_text}{note_text}

【输出要求】：
1. 语言表达精炼直接、重点突出，字数控制在 150 字左右。
2. 严禁在回复中输出任何 emoji 符号。
3. 请以专业、得体、富有启发性的语气，使用整洁规范的 Markdown 格式为主人呈现解答。"""
        return prompt.strip()
