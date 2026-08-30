import unittest
from src.agents.base import PositionSnapshot, AgentRequest
from src.agents.echo_agent import EchoAgent
from src.agents.llm_agent import LLMAgent
from src.agents.prompt_builder import PromptBuilder
from src.controller.teaching_triggers import TeachingTriggers


class TestAgents(unittest.TestCase):
    def test_echo_agent_reply(self):
        agent = EchoAgent()
        snapshot = PositionSnapshot(
            fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            pgn="1. e4 *",
            turn="Black",
            legal_move_count=20,
            in_check=False,
        )
        req = AgentRequest(
            user_message="Hello Maid",
            persona_prompt="You are a helpful maid.",
            snapshot=snapshot,
        )
        reply = agent.reply(req)
        self.assertIn("rnbqkbnr", reply)
        self.assertIn("Hello Maid", reply)

    def test_llm_agent_fallback_and_endpoints(self):
        agent = LLMAgent(api_base="https://api.deepseek.com", api_key="")
        snapshot = PositionSnapshot(
            fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            pgn="1. e4 *",
            turn="Black",
            legal_move_count=20,
            in_check=False,
        )
        req = AgentRequest(
            user_message="分析当前局面",
            persona_prompt=agent.persona_prompt,
            snapshot=snapshot,
        )
        reply = agent.reply(req)
        self.assertIn("rnbqkbnr", reply)
        self.assertEqual(agent._chat_endpoint(), "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(agent._models_endpoint(), "https://api.deepseek.com/v1/models")

    def test_prompt_builder(self):
        triggers = TeachingTriggers()
        snapshot = PositionSnapshot(
            fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            pgn='1. e4 *',
            turn="Black",
            legal_move_count=20,
            in_check=False,
            last_move_san='e4'
        )
        prompt = PromptBuilder.build_custom_prompt(snapshot, triggers, is_auto_move=False, extra_note="What should I do?")
        self.assertIn("e4", prompt)
        self.assertIn("What should I do?", prompt)


if __name__ == "__main__":
    unittest.main()
