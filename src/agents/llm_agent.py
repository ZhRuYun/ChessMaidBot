"""
真实 LLM API 接入 Agent (模块5 - Agent 接口)
通过 OpenAI 兼容 API (DeepSeek / OpenAI / Ollama / vLLM 等) 接入真实 LLM

环境变量配置:
  LLM_API_BASE        - API 基地址 (默认: https://api.deepseek.com)
  LLM_API_KEY         - API 密钥 (默认空, 不设则回退到本地描述性回复)
  LLM_MODEL           - 模型名称 (默认: deepseek-chat)
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
import urllib.request
import urllib.error
from typing import Optional, Any

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
        self.model = model or os.environ.get("LLM_MODEL", "deepseek-chat")
        self.timeout = timeout
        self.max_tokens = int(os.environ.get("LLM_MAX_TOKENS", str(max_tokens)))

        env_reasoning = os.environ.get("LLM_REASONING_EFFORT", "auto")
        self.reasoning_effort = (reasoning_effort if reasoning_effort is not None else env_reasoning).strip().lower()

        env_stream = os.environ.get("LLM_STREAM", "false").strip().lower() in ("true", "1", "yes")
        self.stream = stream if stream is not None else env_stream
        self.show_tool_records = False  # 是否在回复末尾附带简短的工具调用记录 (便于调试)

        default_persona = (
            "你是一位精通国际象棋且温柔细致的AI棋艺女仆助理【ChessMaid】。"
            "你的任务是陪伴主人对弈并学习国际象棋。"
            "回复请保持简洁精炼，重点突出棋理与战术，避免冗长废话。严禁使用任何emoji表情符号。"
            "保持礼貌、体贴且专业的语气。"
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

    def reply(self, request: AgentRequest) -> str:
        """根据标准请求包调用 LLM API 并返回 Markdown 回复; API 不可用时回退"""
        tool_logs: list[str] = []
        if request.tools:
            if request.tools.read_database:
                tool_logs.append("read_database(opening)")
            if request.tools.read_engine_state:
                tool_logs.append("read_engine_state(analyse)")
            if request.tools.web_search:
                tool_logs.append("web_search")

        # 若 API Key 为空, 直接回退
        if not self.api_key:
            res = self._fallback_reply(request)
        else:
            messages = self._build_messages(request)
            try:
                raw = self._call_chat_api(messages)
                res = raw.strip()
            except Exception:
                res = self._fallback_reply(request)

        if self.show_tool_records and tool_logs:
            res += f"\n\n*(工具调用记录: {', '.join(tool_logs)})*"
        return res

    # ---------- 消息组装 ----------

    def _build_messages(self, request: AgentRequest) -> list[dict]:
        """将 AgentRequest 组装为 LLM Chat 消息列表

        消息结构:
          [0] system  = 人设 Prompt + 局面快照上下文 + 引擎评估上下文(可选)
          [1..N]      = dialog_history 中的历史对话
          [N+1] user  = 当前用户消息
        """
        system_msg = request.persona_prompt or self.persona_prompt

        # 注入局面快照上下文 (FEN / PGN / 回合方 / 将军状态等)
        context_block = self._build_context_block(request)
        if context_block:
            system_msg += "\n\n" + context_block

        messages: list[dict] = [{"role": "system", "content": system_msg}]

        # 透传历史对话
        for turn in request.dialog_history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant", "system"):
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": request.user_message})
        return messages

    def _build_context_block(self, request: AgentRequest) -> str:
        """构建局面上下文文本块: 快照信息 + 引擎评估(可选)

        所有外部工具调用均包裹在 try/except 中, 确保任何异常都不影响主链路。
        """
        parts: list[str] = []

        # 1. 局面快照 (始终注入, 这是 LLM 分析棋局的基础)
        snap = request.snapshot
        parts.append(self._format_snapshot(snap))

        # 2. 数据库开局/残局/历史走法知识 (可选)
        db_context = self._fetch_db_context(request)
        if db_context:
            parts.append(db_context)

        # 3. 引擎实时评估 (仅当 tools 可用时主动读取, 失败则静默跳过)
        engine_eval = self._fetch_engine_eval(request)
        if engine_eval:
            parts.append(engine_eval)

        return "\n\n".join(parts)

    def _fetch_db_context(self, request: AgentRequest) -> str:
        """通过 AgentTools 读取开局库/战术库/残局知识"""
        tools = request.tools
        if tools is None or tools.read_database is None:
            return ""
        try:
            # 尝试查询开局库
            opening_data = tools.read_database("opening", {"fen": request.snapshot.fen})
            if opening_data and isinstance(opening_data, dict) and opening_data.get("available"):
                moves = opening_data.get("moves", [])
                if moves:
                    move_strs = [f"{m.get('san', m.get('uci'))} (权重:{m.get('weight', 0)})" for m in moves[:3]]
                    return f"【开局库推荐候选走法】: {', '.join(move_strs)}"
        except Exception:
            pass
        return ""

    @staticmethod
    def _format_snapshot(snap: PositionSnapshot) -> str:
        """将 PositionSnapshot 格式化为 LLM 可读的棋盘上下文文本"""
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
        # PGN 棋谱 (仅在非空时附加, 避免无意义的长文本)
        pgn_text = (snap.pgn or "").strip()
        if pgn_text:
            lines.append("- 完整 PGN 棋谱:")
            lines.append(f"```pgn\n{pgn_text}\n```")
        return "\n".join(lines)

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

    def _call_chat_api(self, messages: list[dict]) -> str:
        """调用 OpenAI 兼容 /v1/chat/completions 接口, 返回回复文本 (支持 stream 与 reasoning_effort)"""
        url = self._chat_endpoint()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": 0.7,
        }

        # OpenAI 标准规范: reasoning_effort ("low", "medium", "high")
        if self.reasoning_effort and self.reasoning_effort not in ("auto", "none", ""):
            payload["reasoning_effort"] = self.reasoning_effort

        if self.stream:
            payload["stream"] = True

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            if self.stream:
                return self._parse_stream_response(resp)
            body = resp.read().decode("utf-8")

        result = json.loads(body)
        choices = result.get("choices", [])
        if not choices:
            raise ValueError("API 返回空 choices")
        content = choices[0].get("message", {}).get("content", "")
        if not content.strip():
            raise ValueError("API 返回空内容")
        return content

    def _parse_stream_response(self, resp) -> str:
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
                except Exception:
                    continue
        full_content = "".join(chunks).strip()
        if not full_content:
            raise ValueError("流式输出返回空内容")
        return full_content

    def _chat_endpoint(self) -> str:
        """拼装 Chat Completions 端点 URL"""
        base = self.api_base.rstrip("/")
        base_lower = base.lower()
        # Ollama 使用 /api/chat; OpenAI 兼容使用 /v1/chat/completions
        # 检测: 1) URL 中包含 ollama 关键字; 2) 端口为默认 Ollama 端口 11434 且路径不含 /v1
        is_ollama = ("ollama" in base_lower) or (":11434" in base_lower and not base_lower.endswith("/v1"))
        if is_ollama:
            return f"{base}/api/chat"
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return f"{base}/chat/completions"

    def get_move(self, request: AgentRequest) -> Optional[str]:
        """为女仆陪练模式 (VS_MAID_LLM) 计算下一步走法 (返回 UCI 格式字符串如 'e2e4')"""
        # 构建获取单步走法的专属 prompt
        fen = request.snapshot.fen
        prompt = (
            f"你现在作为国际象棋陪练选手执棋。当前局面 FEN 为: `{fen}`。\n"
            "请严格以纯文本格式输出一步最佳合法着法（必须为 UCI 格式，如 'e7e5', 'g1f3'，严禁输出任何额外多余文字、标点或解释）。"
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
                # 提取可能的 UCI 着法
                import re
                import chess
                board = chess.Board(fen)
                matches = re.findall(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b", reply.lower())
                for m in matches:
                    try:
                        move = chess.Move.from_uci(m)
                        if move in board.legal_moves:
                            return m
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
        import chess, random
        board = chess.Board(fen)
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
