import unittest
from src.agents.base import PositionSnapshot, AgentTools, AgentRequest
from src.agents.echo_agent import EchoAgent
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
