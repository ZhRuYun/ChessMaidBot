import unittest
from src.agents.base import PositionSnapshot, AgentRequest
from src.agents.echo_agent import EchoAgent
from src.agents.llm_agent import LLMAgent, ResilientStreamParser
from src.agents.prompt_builder import PromptBuilder
from src.agents.memory import ShortTermMemory, LongTermMemory
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
        
        chunks = []
        def _on_chunk(c):
            chunks.append(c)

        reply = agent.reply(req, on_chunk=_on_chunk)
        self.assertIn("rnbqkbnr", reply)
        self.assertTrue(len(chunks) > 0)
        self.assertEqual(agent._chat_endpoint(), "https://api.deepseek.com/v1/chat/completions")

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
        self.assertIn("BEGIN_TRUSTED_CHESS_DATA", prompt)

    def test_stream_parser_and_memory(self):
        chunks = []
        parser = ResilientStreamParser(on_chunk=lambda c: chunks.append(c))
        parser.feed(b'data: {"choices": [{"delta": {"content": "```python\\nprint(1)"}}]}\n\n')
        parser.feed(b'data: [DONE]\n\n')
        res = parser.get_result()
        self.assertTrue(res.endswith("```"))

        st_mem = ShortTermMemory(max_turns=3)
        st_mem.add_turn("user", "1")
        st_mem.add_turn("assistant", "2")
        st_mem.add_turn("user", "3")
        st_mem.add_turn("assistant", "4")
        self.assertEqual(len(st_mem.get_messages()), 3)


if __name__ == "__main__":
    unittest.main()
