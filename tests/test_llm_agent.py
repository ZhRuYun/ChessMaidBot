"""
LLMAgent 单元测试
- 验证无 API Key 时自动回退到本地描述性回复
- 验证消息构建逻辑 (system / history / user)
- 验证人设 Prompt 动态更新 (set_persona)
- 验证 API 端点构建逻辑 (Ollama vs OpenAI 兼容)
"""
import os
import json
import unittest
from unittest.mock import patch, MagicMock

from src.agents.llm_agent import LLMAgent
from src.agents.base import AgentRequest, PositionSnapshot, AgentTools


def _make_snapshot(**overrides) -> PositionSnapshot:
    """构造一个标准的 PositionSnapshot 用于测试"""
    base = PositionSnapshot(
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        turn="白方 (White)",
        legal_move_count=20,
        in_check=False,
        last_move_san="",
        game_over_reason="",
        pgn="",
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _make_request(snapshot=None, user_message="test", persona_prompt=None,
                  dialog_history=None, tools=None) -> AgentRequest:
    """构造 AgentRequest"""
    return AgentRequest(
        snapshot=snapshot or _make_snapshot(),
        user_message=user_message,
        persona_prompt=persona_prompt,
        dialog_history=dialog_history or [],
        tools=tools,
    )


class TestLLMAgentFallback(unittest.TestCase):
    """无 API Key 时的回退逻辑测试"""

    def setUp(self):
        # 确保环境变量中无 Key, 强制走降级路径
        with patch.dict(os.environ, {}, clear=True):
            self.agent = LLMAgent(api_key="")

    def test_no_api_key_returns_fallback(self):
        req = _make_request(user_message="你好")
        reply = self.agent.reply(req)
        self.assertIn("主人", reply)
        self.assertIn("本地回退", reply)
        self.assertIn("LLM", reply)

    def test_fallback_contains_snapshot_info(self):
        snap = _make_snapshot(turn="黑方 (Black)", legal_move_count=15,
                              last_move_san="e4")
        req = _make_request(snapshot=snap)
        reply = self.agent.reply(req)
        self.assertIn("黑方", reply)
        self.assertIn("15", reply)
        self.assertIn("e4", reply)

    def test_fallback_game_over(self):
        snap = _make_snapshot(game_over_reason="将死 (Checkmate)")
        req = _make_request(snapshot=snap)
        reply = self.agent.reply(req)
        self.assertIn("已经结束", reply)
        self.assertIn("Checkmate", reply)


class TestLLMAgentMessageBuilding(unittest.TestCase):
    """_build_messages 消息组装逻辑测试"""

    def setUp(self):
        self.agent = LLMAgent(api_key="sk-fake")

    def test_system_message_contains_persona(self):
        persona = "你是一位测试助手。"
        req = _make_request(persona_prompt=persona)
        msgs = self.agent._build_messages(req)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("测试助手", msgs[0]["content"])

    def test_system_message_contains_fen(self):
        req = _make_request()
        msgs = self.agent._build_messages(req)
        sys_content = msgs[0]["content"]
        self.assertIn("FEN", sys_content)
        self.assertIn("rnbqkbnr", sys_content)

    def test_dialog_history_passthrough(self):
        history = [
            {"role": "user", "content": "第一步"},
            {"role": "assistant", "content": "回复一"},
        ]
        req = _make_request(dialog_history=history, user_message="第二步")
        msgs = self.agent._build_messages(req)
        # system + 2 history + 1 user = 4
        self.assertEqual(len(msgs), 4)
        self.assertEqual(msgs[1]["role"], "user")
        self.assertEqual(msgs[1]["content"], "第一步")
        self.assertEqual(msgs[2]["role"], "assistant")
        self.assertEqual(msgs[3]["role"], "user")
        self.assertEqual(msgs[3]["content"], "第二步")

    def test_invalid_history_role_skipped(self):
        history = [{"role": "weird_role", "content": "x"}]
        req = _make_request(dialog_history=history)
        msgs = self.agent._build_messages(req)
        # system + user, 无效角色被跳过
        self.assertEqual(len(msgs), 2)

    def test_pgn_attached_when_present(self):
        snap = _make_snapshot(pgn="1. e4 e5 2. Nf3 Nc6")
        req = _make_request(snapshot=snap)
        msgs = self.agent._build_messages(req)
        sys_content = msgs[0]["content"]
        self.assertIn("1. e4 e5", sys_content)

    def test_in_check_flag(self):
        snap = _make_snapshot(in_check=True)
        req = _make_request(snapshot=snap)
        msgs = self.agent._build_messages(req)
        self.assertIn("将军", msgs[0]["content"])


class TestLLMAgentPersona(unittest.TestCase):
    """人设 Prompt 动态更新测试"""

    def test_set_persona_updates_default(self):
        agent = LLMAgent(api_key="")
        new_persona = "我是新的人设。"
        agent.set_persona(new_persona)
        self.assertEqual(agent.persona_prompt, new_persona)

    def test_set_persona_ignores_empty(self):
        agent = LLMAgent(api_key="", persona_prompt="原始人设")
        agent.set_persona("   ")
        self.assertEqual(agent.persona_prompt, "原始人设")
        agent.set_persona("")
        self.assertEqual(agent.persona_prompt, "原始人设")

    def test_request_persona_overrides_agent_default(self):
        agent = LLMAgent(api_key="sk-fake", persona_prompt="Agent 默认人设")
        req = _make_request(persona_prompt="请求覆盖人设")
        msgs = agent._build_messages(req)
        self.assertIn("请求覆盖人设", msgs[0]["content"])
        self.assertNotIn("Agent 默认人设", msgs[0]["content"])


class TestLLMAgentEndpoint(unittest.TestCase):
    """API 端点 URL 构建测试"""

    def test_openai_default(self):
        agent = LLMAgent(api_base="https://api.openai.com", api_key="x")
        self.assertEqual(
            agent._chat_endpoint(),
            "https://api.openai.com/v1/chat/completions"
        )

    def test_deepseek_default(self):
        agent = LLMAgent(api_base="https://api.deepseek.com", api_key="x")
        self.assertEqual(
            agent._chat_endpoint(),
            "https://api.deepseek.com/v1/chat/completions"
        )

    def test_already_has_v1_not_duplicated(self):
        agent = LLMAgent(api_base="https://api.example.com/v1", api_key="x")
        self.assertEqual(
            agent._chat_endpoint(),
            "https://api.example.com/v1/chat/completions"
        )

    def test_ollama_by_keyword(self):
        agent = LLMAgent(api_base="http://localhost:11434", api_key="x")
        url = agent._chat_endpoint()
        self.assertIn("/api/chat", url)
        self.assertNotIn("/v1/", url)

    def test_ollama_explicit_name(self):
        agent = LLMAgent(api_base="http://my-ollama.internal:11434", api_key="x")
        # 包含端口 11434 且路径不含 /v1 => Ollama 分支
        url = agent._chat_endpoint()
        self.assertIn("/api/chat", url)


class TestLLMAgentEngineEval(unittest.TestCase):
    """引擎评估上下文注入测试"""

    def test_no_tools_returns_empty(self):
        agent = LLMAgent(api_key="")
        req = _make_request(tools=None)
        self.assertEqual(agent._fetch_engine_eval(req), "")

    def test_game_over_skips_eval(self):
        agent = LLMAgent(api_key="")
        tools = MagicMock(spec=AgentTools)
        snap = _make_snapshot(game_over_reason="将死")
        req = _make_request(snapshot=snap, tools=tools)
        self.assertEqual(agent._fetch_engine_eval(req), "")
        tools.read_engine_state.assert_not_called()

    def test_tools_exception_handled(self):
        agent = LLMAgent(api_key="")
        tools = MagicMock(spec=AgentTools)
        tools.read_engine_state.side_effect = RuntimeError("boom")
        req = _make_request(tools=tools)
        # 不抛出异常, 静默返回空
        self.assertEqual(agent._fetch_engine_eval(req), "")

    def test_valid_analysis_formatted(self):
        agent = LLMAgent(api_key="")
        tools = MagicMock(spec=AgentTools)
        tools.read_engine_state.return_value = {
            "available": True,
            "analysis": [
                {"score_cp": 32, "pv": ["e2e4", "e7e5", "g1f3"]},
            ],
        }
        req = _make_request(tools=tools)
        result = agent._fetch_engine_eval(req)
        self.assertIn("Stockfish", result)
        self.assertIn("32", result)
        self.assertIn("e2e4", result)


class TestLLMAgentAPICall(unittest.TestCase):
    """_call_chat_api 测试 (使用 mock)"""

    @patch("urllib.request.urlopen")
    def test_successful_api_call(self, mock_urlopen):
        mock_resp = MagicMock()
        # 使用 UTF-8 编码的 JSON 字节串 (避免 bytes literal 含非 ASCII)
        mock_resp.read.return_value = (
            '{"choices":[{"message":{"content":"你好，主人！"}}]}'
            .encode("utf-8")
        )
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        agent = LLMAgent(api_key="sk-fake")
        result = agent._call_chat_api([
            {"role": "user", "content": "hi"}
        ])
        self.assertEqual(result, "你好，主人！")

    @patch("urllib.request.urlopen")
    def test_empty_choices_raises(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"choices":[]}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        agent = LLMAgent(api_key="sk-fake")
        with self.assertRaises(ValueError):
            agent._call_chat_api([{"role": "user", "content": "hi"}])

    @patch("urllib.request.urlopen")
    def test_successful_stream_api_call(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__iter__.return_value = [
            b'data: {"choices":[{"delta":{"content":"\xe4\xbd\xa0\xe5\xa5\xbd"}}]}\n',
            b'data: {"choices":[{"delta":{"content":"\xef\xbc\x8c\xe4\xb8\xbb\xe4\xba\xba\xef\xbc\x81"}}]}\n',
            b'data: [DONE]\n',
        ]
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        agent = LLMAgent(api_key="sk-fake", stream=True)
        result = agent._call_chat_api([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "你好，主人！")

    @patch("urllib.request.urlopen")
    def test_reasoning_effort_in_payload(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"choices":[{"message":{"content":"ok"}}]}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        agent = LLMAgent(api_key="sk-fake", reasoning_effort="high")
        agent._call_chat_api([{"role": "user", "content": "hi"}])

        called_req = mock_urlopen.call_args[0][0]
        body = json.loads(called_req.data.decode("utf-8"))
        self.assertEqual(body.get("reasoning_effort"), "high")

    def test_reply_falls_back_on_network_error(self):
        agent = LLMAgent(api_key="sk-fake")
        with patch.object(agent, "_call_chat_api", side_effect=ConnectionError("no net")):
            req = _make_request(user_message="hi")
            reply = agent.reply(req)
            self.assertIn("本地回退", reply)


if __name__ == "__main__":
    unittest.main()
