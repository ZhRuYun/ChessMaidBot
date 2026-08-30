"""
真实 LLM API 接入 Agent (模块5 - Agent 接口)
通过 OpenAI 兼容 API (DeepSeek / OpenAI / Ollama / vLLM 等) 接入真实 LLM

环境变量配置:
  LLM_API_BASE        - API 基地址 (默认: https://api.deepseek.com)
  LLM_API_KEY         - API 密钥 (默认空, 不设则回退到本地描述性回复)
  LLM_MODEL           - 模型名称 (默认: deepseek-v4-flash)
  LLM_TIMEOUT         - 请求超时秒数 (默认: 60)
  LLM_MAX_TOKENS      - 最大生成 token 数 (默认: 1024)
  LLM_REASONING_EFFORT - 思考档位 / 推理强度 (默认: "auto", 可选 "auto", "low", "medium", "high", "none")
  LLM_STREAM          - 是否启用流式输出 (默认: False)

设计要点:
  1. 将局面快照 (FEN / PGN / 回合方 / 将军状态) 注入 system 消息, 确保 LLM 始终拥有棋盘上下文
  2. 当 AgentTools 可用时, 主动读取 Stockfish 引擎评估并注入上下文 (含异常容错)
  3. 支持 OpenAI 标准兼容的 reasoning_effort 参数与 stream 模式解析
  4. API 不可用或 Key 未配置时, reply() 自动回退到内置描述性文本, 保证链路易用
"""
import json
import os
import random
import re
import urllib.request
import urllib.error
from typing import Optional, Any, Callable, List, Dict

import chess

from .base import AgentRequest, ChessAgent, PositionSnapshot


class LLMAgent(ChessAgent):
    """真实 LLM API 接入代理"""

    name = "llm"

    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
        max_tokens: int = 1024,
        reasoning_effort: Optional[str] = None,
        stream: Optional[bool] = None,
        persona_prompt: Optional[str] = None,
    ):
        """
        初始化 LLMAgent。

        参数:
            api_base:         API 基地址, 如 https://api.deepseek.com 或 http://localhost:11434/v1
            api_key:          API 密钥, 不传则从环境变量 LLM_API_KEY 读取
            model:            模型名称, 如 deepseek-chat、gpt-4o、deepseek-reasoner
            timeout:          请求超时秒数
            max_tokens:       最大生成 token 数
            reasoning_effort: 思考档位/推理强度 ("auto", "low", "medium", "high", "none")
            stream:           是否开启流式输出 (SSE 聚合解析)
            persona_prompt:   女仆人设 Prompt, 不传则从环境变量或默认值读取
        """
        self.api_base = api_base or os.environ.get("LLM_API_BASE", "https://api.deepseek.com")
        # 兼容 Ollama 等本地无 Key 服务
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "deepseek-v4-flash")
        self.timeout = timeout
        self.max_tokens = int(os.environ.get("LLM_MAX_TOKENS", str(max_tokens)))

        env_reasoning = os.environ.get("LLM_REASONING_EFFORT", "auto")
        self.reasoning_effort = (reasoning_effort if reasoning_effort is not None else env_reasoning).strip().lower()

        env_stream = os.environ.get("LLM_STREAM", "false").strip().lower() in ("true", "1", "yes")
        self.stream = stream if stream is not None else env_stream
        self.show_tool_records = False  # 是否在回复末尾附带简短的工具调用记录 (便于调试)

        default_persona = (
            "你是一位精通国际象棋且温柔细致的AI棋艺女仆助理【ChessMaid】。"
            "你的核心职责是陪伴主人对弈并提供富有洞察力的战术指导与大局观教学。"
            "在解答与指导时：\n"
            "1. 语言亲切得体、精炼精准，优先剖析空间、子力协调、王安全与关键格控制等核心棋理。\n"
            "2. 指出走法意图与战术威胁，给出清晰可行的后续计划。\n"
            "3. 对局未结束时必须提供3个合法候选着法（格式：着法：说明），每行只保留核心意图、主要后续与必要防范；完整回答控制在150字以内。\n"
            "4. 终局时用2至3句总结胜负手与关键转折。严禁废话与套话，严禁输出任何emoji表情符号。"
        )
        self.persona_prompt = persona_prompt or default_persona

    def set_persona(self, persona_prompt: str):
        """运行时更新人设 Prompt (无需重建实例)

        Args:
            persona_prompt: 新的人设字符串; 为空则忽略 (保留原值)
        """
        if persona_prompt and persona_prompt.strip():
            self.persona_prompt = persona_prompt.strip()

    # ---------- ChessAgent 接口 ----------

    def _get_tools_definitions(self, request: AgentRequest) -> list[dict]:
        """构造 OpenAI 标准 Tool Call / Function Calling 规范定义"""
        if not request.tools:
            return []
        tools = []
        if getattr(request.tools, "read_engine_state", None):
            tools.append({
                "type": "function",
                "function": {
                    "name": "engine_analyze",
                    "description": "调用 Stockfish 国际象棋引擎分析指定局面 FEN 或当前局面，获取最佳候选走法及评分。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fen": {"type": "string", "description": "待分析的局面 FEN 字符串，不传则默认当前棋盘局面"},
                            "depth": {"type": "integer", "description": "搜索深度 (默认 12)", "default": 12},
                            "multipv": {"type": "integer", "description": "多主变例分析条数 (1~3, 默认 2)", "default": 2}
                        },
                    }
                }
            })
        if getattr(request.tools, "query_opening", None) or getattr(request.tools, "read_database", None):
            tools.append({
                "type": "function",
                "function": {
                    "name": "query_opening_book",
                    "description": "查询开局库获取当前或指定局面的开局名称、谱着走法及权重推荐。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fen": {"type": "string", "description": "待查询的局面 FEN 字符串，不传则默认当前棋盘局面"}
                        }
                    }
                }
            })
        if getattr(request.tools, "query_history", None):
            tools.append({
                "type": "function",
                "function": {
                    "name": "query_game_history",
                    "description": "检索历史归档棋局及其总结，辅助复盘或对比历史走法。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "返回历史对局条数 (默认 3)", "default": 3}
                        }
                    }
                }
            })
        if getattr(request.tools, "web_search", None):
            tools.append({
                "type": "function",
                "function": {
                    "name": "search_chess_knowledge",
                    "description": "联网搜索国际象棋知识、特级大师对局历史、战术术语或棋理理论。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "搜索关键词或问题"}
                        },
                        "required": ["query"]
                    }
                }
            })
        return tools

    def _execute_tool_call(self, request: AgentRequest, name: str, args: dict) -> str:
        """执行具体的 Tool Function 并返回 JSON 字符串结果"""
        tools = request.tools
        if not tools:
            return json.dumps({"error": "No tools available"})
        try:
            if name == "engine_analyze":
                fen = args.get("fen") or request.snapshot.fen
                depth = args.get("depth", 12)
                multipv = args.get("multipv", 2)
                if tools.read_engine_state:
                    res = tools.read_engine_state("analyse", {"fen": fen, "depth": depth, "multipv": multipv})
                    return json.dumps(res, ensure_ascii=False)
            elif name == "query_opening_book":
                fen = args.get("fen") or request.snapshot.fen
                if getattr(tools, "query_opening", None):
                    res = tools.query_opening(fen, 5)
                    return json.dumps(res, ensure_ascii=False)
                elif getattr(tools, "read_database", None):
                    res = tools.read_database("opening", {"fen": fen, "limit": 5})
                    return json.dumps(res, ensure_ascii=False)
            elif name == "query_game_history":
                limit = args.get("limit", 3)
                if getattr(tools, "query_history", None):
                    res = tools.query_history(limit, True)
                    return json.dumps(res, ensure_ascii=False)
            elif name == "search_chess_knowledge":
                q = args.get("query", "")
                if getattr(tools, "web_search", None) and q:
                    res = tools.web_search(q)
                    return json.dumps({"search_result": res}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        return json.dumps({"error": f"Tool {name} not handled"}, ensure_ascii=False)

    def reply(self, request: AgentRequest, on_chunk: Optional[Callable[[str], None]] = None) -> str:
        """根据标准请求包调用 LLM API 并返回 Markdown 回复; 支持 Tool Calling 与流式回调; API 不可用时回退"""
        tool_logs: list[str] = []
        snap = request.snapshot
        is_game_over = bool(snap.game_over_reason)
        should_query_opening = not is_game_over and len((snap.pgn or "").split()) <= 20
        should_query_engine = not is_game_over

        if request.tools:
            if should_query_opening and (getattr(request.tools, "query_opening", None) or getattr(request.tools, "read_database", None)):
                tool_logs.append("query_opening")
            if is_game_over and getattr(request.tools, "query_history", None):
                tool_logs.append("query_history")
            if should_query_engine and getattr(request.tools, "read_engine_state", None):
                tool_logs.append("read_engine_state")
            if getattr(request.tools, "web_search", None) and any(k in request.user_message for k in ("搜索", "历史", "理论", "谁是", "介绍", "什么是")):
                tool_logs.append("web_search")

        if not self.api_key:
            res = self._fallback_reply(request)
            if on_chunk:
                on_chunk(res)
            return res

        messages = self._build_messages(request, should_query_opening=should_query_opening, should_query_engine=should_query_engine)
        tool_defs = self._get_tools_definitions(request)

        try:
            # 首次调用: 允许模型进行 Tool Call (最多循环 2 轮)
            for _ in range(2):
                call_res = self._call_chat_api_raw(messages, tools=tool_defs if tool_defs else None, on_chunk=None)
                msg = call_res.get("message", {})
                tool_calls = msg.get("tool_calls")
                if not tool_calls:
                    # 无工具调用，直接输出最终内容
                    final_content = msg.get("content") or ""
                    if not final_content and on_chunk is None:
                        final_content = self._fallback_reply(request)
                    if on_chunk:
                        # 如需流式呈现且刚才未流式输出，回调一次
                        on_chunk(final_content)
                    res = final_content.strip()
                    if self.show_tool_records and tool_logs:
                        res += f"\n\n*(工具调用记录: {', '.join(tool_logs)})*"
                    return res

                # 处理模型发起的 tool_calls
                messages.append(msg)
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    try:
                        fn_args = json.loads(fn.get("arguments", "{}"))
                    except Exception:
                        fn_args = {}
                    tool_logs.append(f"ToolCall:{fn_name}")
                    tool_out = self._execute_tool_call(request, fn_name, fn_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{fn_name}"),
                        "content": tool_out
                    })

            # 工具调用完成后获取最终回答 (开启流式渲染)
            res = self._call_chat_api(messages, on_chunk=on_chunk).strip()
        except Exception:
            res = self._fallback_reply(request)
            if on_chunk:
                on_chunk(res)

        if self.show_tool_records and tool_logs:
            res += f"\n\n*(工具调用记录: {', '.join(tool_logs)})*"
        return res

    # ---------- 消息组装 ----------

    def _build_messages(self, request: AgentRequest, should_query_opening: bool = True, should_query_engine: bool = True) -> list[dict]:
        """将 AgentRequest 组装为 LLM Chat 消息列表

        消息结构:
          [0] system  = 人设 Prompt + 局面快照上下文 + 引擎评估上下文(可选)
          [1..N]      = dialog_history 中的历史对话
          [N+1] user  = 当前用户消息
        """
        system_msg = request.persona_prompt or self.persona_prompt

        # 注入局面快照上下文 (FEN / PGN / 回合方 / 将军状态等)
        context_block = self._build_context_block(request, should_query_opening=should_query_opening, should_query_engine=should_query_engine)
        if context_block:
            system_msg += "\n\n" + context_block

        messages: list[dict] = [{"role": "system", "content": system_msg}]

        # 透传历史对话 (限制最近 8 轮历史，防止长对局 Token 溢出)
        trimmed_history = request.dialog_history[-8:] if len(request.dialog_history) > 8 else request.dialog_history
        for turn in trimmed_history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant", "system"):
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": request.user_message})
        return messages

    def _build_context_block(self, request: AgentRequest, should_query_opening: bool = True, should_query_engine: bool = True) -> str:
        """构建局面上下文文本块: 快照信息 + 引擎评估(可选)

        所有外部工具调用均包裹在 try/except 中, 确保任何异常都不影响主链路。
        """
        parts: list[str] = []

        # 1. 局面快照 (始终注入, 这是 LLM 分析棋局的基础)
        snap = request.snapshot
        parts.append(self._format_snapshot(snap))

        # 2. 开局库推荐走法与名称识别 (按需调用)
        if should_query_opening:
            opening_context = self._fetch_opening_context(request)
            if opening_context:
                parts.append(opening_context)

        # 3. 引擎实时评估 (按需调用)
        if should_query_engine:
            engine_eval = self._fetch_engine_eval(request)
            if engine_eval:
                parts.append(engine_eval)

        return "\n\n".join(parts)

    @staticmethod
    def _format_snapshot(snap: PositionSnapshot) -> str:
        """将 PositionSnapshot 格式化为 LLM 可读的棋盘上下文文本 (精简 token 版)"""
        lines = [
            "【当前棋盘局面】",
            f"- FEN: `{snap.fen}`",
            f"- 当前行动方: {snap.turn}",
            f"- 合法走法数: {snap.legal_move_count}",
        ]
        if snap.in_check:
            lines.append("- 状态: 当前行动方被将军")
        if snap.last_move_san:
            lines.append(f"- 最近一步: {snap.last_move_san}")
        if snap.game_over_reason:
            lines.append(f"- 终局原因: {snap.game_over_reason}")
        # 优化 Token: 仅保留最近 10 步记谱，避免长对局 PGN 膨胀
        pgn_text = (snap.pgn or "").strip()
        if pgn_text:
            lines.append("- 对局 PGN 记谱:")
            # 过滤头部只提取走法行，且限制长度以节省 token
            moves_only = "\n".join([l for l in pgn_text.splitlines() if not l.startswith("[") and l.strip()])
            if len(moves_only) > 300:
                moves_only = "..." + moves_only[-300:]
            lines.append(f"```pgn\n{moves_only or pgn_text}\n```")
        return "\n".join(lines)

    def _fetch_opening_context(self, request: AgentRequest) -> str:
        """通过 AgentTools 主动查询开局库, 返回开局推荐走法或名称上下文"""
        tools = request.tools
        if not tools:
            return ""
        query_func = getattr(tools, "query_opening", None) or getattr(tools, "read_database", None)
        if not query_func:
            return ""

        try:
            if getattr(tools, "query_opening", None):
                res = tools.query_opening(request.snapshot.fen, 5)
            else:
                res = tools.read_database("opening", {"fen": request.snapshot.fen, "limit": 5})
            if not res or not isinstance(res, dict):
                return ""
            
            lines = ["【开局库参考】"]
            opening_name = res.get("opening_name") or res.get("name")
            if opening_name:
                lines.append(f"- 开局名称: {opening_name}")
            moves = res.get("moves") or res.get("candidates") or []
            if moves:
                moves_desc = []
                for m in moves[:4]:
                    if isinstance(m, dict):
                        uci = m.get("uci") or m.get("move")
                        weight = m.get("weight") or m.get("score")
                        moves_desc.append(f"{uci}(权重:{weight})" if weight else str(uci))
                    elif isinstance(m, str):
                        moves_desc.append(m)
                if moves_desc:
                    lines.append(f"- 推荐谱着: {', '.join(moves_desc)}")
            return "\n".join(lines) if len(lines) > 1 else ""
        except Exception:
            return ""

    def _fetch_engine_eval(self, request: AgentRequest) -> str:
        """通过 AgentTools 主动读取 Stockfish 引擎评估, 返回上下文文本块

        - 仅当 request.tools.read_engine_state 可用时调用
        - 使用轻量参数 (depth=10, multipv=1) 避免过度耗时
        - 任何异常均静默降级 (返回空字符串), 不影响 LLM 主链路
        """
        tools = request.tools
        if not tools or not getattr(tools, "read_engine_state", None):
            return ""

        snap = request.snapshot
        # 终局局面无需引擎评估
        if snap.game_over_reason:
            return ""

        try:
            state: Any = tools.read_engine_state(
                state_type="analyse", params={"depth": 10, "multipv": 1}
            )
        except Exception:
            return ""

        if not isinstance(state, dict) or not state.get("available"):
            return ""

        analysis = state.get("analysis") or []
        if not analysis:
            return ""

        return self._format_engine_eval(analysis)

    @staticmethod
    def _format_engine_eval(analysis: list) -> str:
        """将引擎分析结果格式化为 LLM 可读文本"""
        lines = ["【Stockfish 引擎评估】"]
        for i, item in enumerate(analysis[:3], 1):
            score_cp = item.get("score_cp")
            pv = item.get("pv") or []
            # 将 UCI 走法列表转为可读字符串
            pv_str = " ".join(pv[:8]) if pv else "(无)"
            if score_cp is not None:
                lines.append(f"- 候选 {i}: 评分 {score_cp} cp, 主变例: {pv_str}")
            else:
                lines.append(f"- 候选 {i}: 评分 N/A, 主变例: {pv_str}")
        return "\n".join(lines)

    # ---------- API 通信 ----------

    def _call_chat_api_raw(self, messages: list[dict], tools: Optional[list] = None, on_chunk: Optional[Callable[[str], None]] = None) -> dict:
        """底层 Chat Completions 原始调用，返回完整 choice 字典 (包含 tool_calls / message 等)"""
        url = self._chat_endpoint()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": min(self.max_tokens, 1500),
            "temperature": 0.6,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if self.reasoning_effort and self.reasoning_effort not in ("auto", "none", ""):
            payload["reasoning_effort"] = self.reasoning_effort

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "ChessMaidBot/1.0",
            "Connection": "keep-alive",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8")
        result = json.loads(body)
        choices = result.get("choices", [])
        if not choices:
            raise ValueError("API 返回空 choices")
        return choices[0]

    def _call_chat_api(self, messages: list[dict], max_retries: int = 2, on_chunk: Optional[Callable[[str], None]] = None) -> str:
        """调用 OpenAI 兼容 /v1/chat/completions 接口, 支持指数退避重试 (支持 stream 与 reasoning_effort)"""
        url = self._chat_endpoint()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": min(self.max_tokens, 1500),
            "temperature": 0.6,
        }

        # OpenAI 标准规范: reasoning_effort ("low", "medium", "high")
        if self.reasoning_effort and self.reasoning_effort not in ("auto", "none", ""):
            payload["reasoning_effort"] = self.reasoning_effort

        use_stream = self.stream or (on_chunk is not None)
        if use_stream:
            payload["stream"] = True

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "ChessMaidBot/1.0",
            "Connection": "keep-alive",
        }

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    if use_stream:
                        return self._parse_stream_response(resp, on_chunk=on_chunk)
                    body = resp.read().decode("utf-8")

                result = json.loads(body)
                choices = result.get("choices", [])
                if not choices:
                    raise ValueError("API 返回空 choices")
                content = choices[0].get("message", {}).get("content", "")
                if not content.strip():
                    raise ValueError("API 返回空内容")
                if on_chunk:
                    on_chunk(content)
                return content
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as e:
                last_error = e
                if attempt < max_retries:
                    import time
                    time.sleep(0.5 * (attempt + 1))
                    continue

        raise last_error or RuntimeError("LLM API 调用失败")

    def _parse_stream_response(self, resp, on_chunk: Optional[Callable[[str], None]] = None) -> str:
        """解析 SSE (Server-Sent Events) 流式响应数据"""
        chunks = []
        for line_bytes in resp:
            line = line_bytes.decode("utf-8").strip()
            if not line:
                continue
            if line.startswith("data:"):
                raw_data = line[len("data:"):].strip()
                if raw_data == "[DONE]":
                    break
                try:
                    data_obj = json.loads(raw_data)
                    choices = data_obj.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        part = delta.get("content", "")
                        if part:
                            chunks.append(part)
                            if on_chunk:
                                on_chunk(part)
                except Exception:
                    continue
        full_content = "".join(chunks).strip()
        if not full_content:
            raise ValueError("流式输出返回空内容")
        return full_content

    @staticmethod
    def _is_ollama_base(base_lower: str) -> bool:
        """判定 API 基地址是否为 Ollama 服务 (URL 含 ollama 关键字, 或默认端口 11434 且未带 /v1)"""
        return ("ollama" in base_lower) or (":11434" in base_lower and not base_lower.endswith("/v1"))

    def _chat_endpoint(self) -> str:
        """拼装 Chat Completions 端点 URL"""
        base = self.api_base.rstrip("/")
        # Ollama 使用 /api/chat; OpenAI 兼容使用 /v1/chat/completions
        if self._is_ollama_base(base.lower()):
            return f"{base}/api/chat"
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return f"{base}/chat/completions"

    def _models_endpoint(self) -> str:
        """拼装 Models 列表端点 URL"""
        base = self.api_base.rstrip("/")
        if self._is_ollama_base(base.lower()):
            return f"{base}/api/tags"
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return f"{base}/models"

    @classmethod
    def test_connection(cls, api_base: str, api_key: str, timeout: int = 10) -> bool:
        """仅测试 API 连接连通性"""
        base = (api_base or "https://api.deepseek.com").rstrip("/")
        is_ollama = cls._is_ollama_base(base.lower())
        url = f"{base}/api/tags" if is_ollama else (f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models")

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 204)

    @classmethod
    def fetch_models(cls, api_base: str, api_key: str, timeout: int = 10) -> list[str]:
        """仅拉取远端支持的模型列表"""
        return cls.test_connection_and_fetch_models(api_base, api_key, timeout)

    @classmethod
    def test_connection_and_fetch_models(cls, api_base: str, api_key: str, timeout: int = 10) -> list[str]:
        """测试连接并拉取远端支持的模型列表 (静态/类方法，支持在对话框中即时调用)"""
        base = (api_base or "https://api.deepseek.com").rstrip("/")
        is_ollama = cls._is_ollama_base(base.lower())
        url = f"{base}/api/tags" if is_ollama else (f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models")

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")

        data = json.loads(body)
        models = []
        if is_ollama:
            for item in data.get("models", []):
                name = item.get("name") or item.get("model")
                if name:
                    models.append(name)
        else:
            for item in data.get("data", []):
                m_id = item.get("id")
                if m_id:
                    models.append(m_id)

        return models

    def get_move(self, request: AgentRequest) -> Optional[str]:
        """为女仆陪练模式 (VS_MAID_LLM) 计算下一步走法 (返回 UCI 格式字符串如 'e2e4')"""
        # 在与LLM对弈模式下，若LLM判断局势对LLM不利 (例如引擎评估落后过多), 可触发 request_undo
        if request.tools and getattr(request.tools, "read_engine_state", None) and getattr(request.tools, "request_undo", None):
            try:
                state = request.tools.read_engine_state("analyse", {"depth": 8, "multipv": 1})
                if state and state.get("available") and state.get("analysis"):
                    cp = state["analysis"][0].get("score_cp")
                    # 落后超过 350 cp 时判定局势严重不利，向玩家请求悔棋
                    if cp is not None and cp < -350:
                        request.tools.request_undo("女仆感觉当前局势落后过大陷入危机，向主人请求悔棋一步！")
            except Exception:
                pass

        # 构建获取单步走法的专属 prompt
        fen = request.snapshot.fen
        board = chess.Board(fen)
        legal_uci_list = [m.uci() for m in board.legal_moves]
        legal_san_list = [board.san(m) for m in board.legal_moves]

        prompt = (
            f"你现在作为国际象棋陪练选手执棋。当前局面 FEN 为: `{fen}`。\n"
            f"当前所有合法走法列表: {', '.join(legal_uci_list[:30])}\n"
            "请严格以纯文本格式输出一步最佳合法着法（必须为 UCI 格式如 'e7e5' 或 SAN 格式如 'Nf3'，严禁输出任何额外多余文字、标点或解释）。"
        )
        move_req = AgentRequest(
            user_message=prompt,
            persona_prompt=request.persona_prompt,
            snapshot=request.snapshot,
            tools=request.tools,
        )
        
        # 尝试调用 LLM
        if self.api_key:
            try:
                reply = self.reply(move_req)
                # 1. 优先尝试从回复中提取合法的 UCI 着法
                matches = re.findall(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b", reply.lower())
                for m in matches:
                    try:
                        move = chess.Move.from_uci(m)
                        if move in board.legal_moves:
                            return m
                    except Exception:
                        continue
                # 2. 尝试从回复中提取合法的 SAN 记谱
                for san in legal_san_list:
                    if san.lower() in reply.lower():
                        try:
                            move = board.parse_san(san)
                            return move.uci()
                        except Exception:
                            continue
            except Exception:
                pass

        # 若 LLM 无 key 或解析失败，降级使用开局库或引擎/合法走法
        if request.tools and request.tools.read_engine_state:
            try:
                state = request.tools.read_engine_state("best_move", {"movetime_ms": 300})
                if state and state.get("best_move"):
                    return state["best_move"]
            except Exception:
                pass

        # 随机合法着法兜底
        legal_moves = list(board.legal_moves)
        if legal_moves:
            return random.choice(legal_moves).uci()
        return None

    # ---------- 回退逻辑 ----------

    def _fallback_reply(self, request: AgentRequest) -> str:
        """API 不可用时的优雅降级回复"""
        snap = request.snapshot
        if snap.game_over_reason:
            return (
                f"主人，这一局已经结束了呢～ ({snap.game_over_reason})<br>"
                f"最终局面 FEN: `{snap.fen}`<br>"
                f"*(LLM 服务暂时不可用，以上为本地回退信息。)*"
            )
        return (
            f"主人，我已经收到您的提问：*「{request.user_message}」*。<br>"
            f"【当前局面】: 轮到 **{snap.turn}** 行动，共有 **{snap.legal_move_count}** 种合法走法。<br>"
            f"最近一步: {snap.last_move_san or '开局初始'}<br>"
            f"FEN: `{snap.fen}`<br>"
            f"*(LLM 服务暂时不可用或未配置 API Key，以上为本地回退信息。配置 LLM_API_KEY 后即可获得 AI 女仆实时回复。)*"
        )
