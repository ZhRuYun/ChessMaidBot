"""
PromptBuilder 提示词生成器与 LLM 教学定制化 单元测试
"""
import unittest
import chess
from src.agents.prompt_builder import PromptBuilder
from src.agents.base import PositionSnapshot
from src.controller.teaching_triggers import TeachingTriggers


class TestPromptBuilder(unittest.TestCase):
    def setUp(self):
        self.snapshot = PositionSnapshot(
            fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            pgn='[Event "Casual"]\n\n1. e4 e5 *',
            turn="白方",
            legal_move_count=29,
            in_check=False,
            last_move_san="e5",
            game_over_reason="",
        )

    def test_all_switches_enabled_prompt(self):
        triggers = TeachingTriggers(
            master_enabled=True,
            eval_current_position=True,
            suggest_moves=True,
            eval_history_moves=True,
            game_over_summary=True,
        )
        prompt = PromptBuilder.build_custom_prompt(self.snapshot, triggers, is_auto_move=True, game_mode_name="vs_engine")
        self.assertIn("当下局面评估", prompt)
        self.assertIn("建议着法推荐", prompt)
        self.assertIn("历史走法评估", prompt)
        self.assertIn("落子自动教学触发", prompt)
        self.assertIn("当前游戏模式: vs_engine", prompt)
        self.assertIn("e5", prompt)
        self.assertIn("PGN", prompt)
        self.assertIn("FEN", prompt)

    def test_partial_switches_prompt(self):
        triggers = TeachingTriggers(
            master_enabled=True,
            eval_current_position=True,
            suggest_moves=False,
            eval_history_moves=False,
            game_over_summary=False,
        )
        prompt = PromptBuilder.build_custom_prompt(self.snapshot, triggers, is_auto_move=False)
        self.assertIn("当下局面评估", prompt)
        self.assertNotIn("建议着法推荐", prompt)
        self.assertNotIn("历史走法评估", prompt)
        self.assertIn("主动询问女仆教学指导", prompt)

    def test_all_sub_switches_disabled_fallback(self):
        triggers = TeachingTriggers(
            master_enabled=True,
            eval_current_position=False,
            suggest_moves=False,
            eval_history_moves=False,
            game_over_summary=False,
        )
        prompt = PromptBuilder.build_custom_prompt(self.snapshot, triggers)
        self.assertIn("棋理剖析", prompt)


if __name__ == "__main__":
    unittest.main()
