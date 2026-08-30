# AGENTS.md - Agent 模块体系与二次开发规范

> **【强制执行令】致所有阅读此文件的 AI 模型与开发者：**
> 本规范详述 ChessMaidBot 的 Agent 模块架构设计、工具调用体系、Prompt 打包标准及二次开发规范。

---

## 1. Agent 模块核心架构与职责

Agent 模块（`src/agents/`）负责大语言模型交互、提示词标准化装配、外部工具调用与对局辅助决策。

```
src/agents/
├── __init__.py
├── base.py            # Agent 抽象基类 (ChessAgent)、请求结构体 (AgentRequest)、局面快照 (PositionSnapshot) 与工具定义 (AgentTools)
├── llm_agent.py       # 真实 LLM API 接入实现 (OpenAI 兼容 / DeepSeek / Ollama / vLLM)
├── echo_agent.py      # 本地降级回退 Agent
└── prompt_builder.py  # 教学提示词动态装配器
```

---

## 2. Agent 可调用的工具列表 (AgentTools & Function Calling)

当 `GameController` 组装 `AgentRequest` 时，会通过 `AgentTools` 将系统工具库注入给 Agent，并通过 OpenAI 标准 JSON Schema 工具声明提供自主 Tool Call 能力：

| 工具名称 / 接口 | 对应方法 | 支持参数与功能 | 说明 |
|---|---|---|---|
| **开局库查询** (`query_opening_book` / `query_opening`) | `history_store.query_database(category="opening", ...)` | `fen="rnbqkbnr/..."` (查询开局名称、ECO 编码及候选走法权重) | 基于 Lichess 开局库，未提供 FEN 时自动注入当前局面 |
| **历史对局检索** (`query_game_history` / `query_history`) | `history_store.query_database(category="history", ...)` | `limit=5, filter_useless=True` (检索已归档历史对局及总结) | 仅检索玩家正常完赛的有效对局 |
| **引擎深度分析** (`engine_analyze` / `read_engine_state`) | `stockfish_client.get_state(state_type, ...)` | `depth=12, multipv=2` (多候选线评估、score_cp 分数与 PV 主变例) | Agent 自主根据玩家问题推演指定局面 |
| **联网知识搜索** (`search_chess_knowledge` / `web_search`) | `game_controller._agent_web_search(query)` | `query="国际象棋 西西里防御 纳道尔夫变例"` | 为 LLM 提供开放 API 检索国际象棋战术理论与知识摘要 |
| **向玩家发送悔棋请求** (`request_undo`) | `game_controller._agent_request_undo(reason)` | `reason="局势落后过大"` | 与LLM对弈模式下，LLM判断局势不利时向玩家发送悔棋请求 |

---

## 3. 自定义提示词格式 (Persona Prompt)

人设 Prompt 用于约束 Agent 的语气性格与教学风格。

### 格式要求：
- 建议以角色声明开始，定义身份定位（如温柔女仆、严厉教练等）。
- 明确禁止输出冗长套话，建议限定回复长度（如 150 字以内）。
- 明确禁止使用 emoji 表情符号。

### 示例模版：
```text
你是一位精通国际象棋且温柔细致的AI棋艺女仆助理【ChessMaid】。
你的任务是陪伴主人对弈并学习国际象棋。
回复请保持简洁精炼，重点突出棋理与战术，避免冗长废话。严禁使用任何emoji表情符号。
保持礼貌、体贴且专业的语气。
```

---

## 4. 打包发送给 Agent 的标准 Prompt 格式

通过 `PromptBuilder.build_custom_prompt()` 动态构建发送给 LLM 的完整 Prompt：

```markdown
【玩家落子自动教学触发 / 主动询问女仆教学指导】
请根据以下国际象棋对局信息提供指导：

【棋盘现状】
- 当前游戏模式: vs_engine (扮演双方棋手 / 人机对弈 / 女仆陪练 / 网络对战)
- 局势状态: 对弈中 / 已终局 (原因)
- 当前行动方: 白方 / 黑方
- 最近一步: e4 / 开局初始
- 当前 FEN 码: `rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1`
- 完整对局 PGN:
```pgn
[Event "ChessMaidBot Casual Game"]
[Site "Localhost"]
[Date "2026.08.24"]
[White "Player"]
[Black "Stockfish (Elo 1500)"]
[Result "*"]

1. e4 *
```

【分析解答要点】：
1. 当下局面评估：... (对应 eval_current_position)
2. 建议着法推荐：... (对应 suggest_moves)
3. 历史走法评估 (失误预警)：... (对应 eval_history_moves)
4. 棋局结束总结 (赛后复盘)：... (对应 game_over_summary)

【输出要求】：
1. 语言表达请务必精炼短小、直击要害，拒绝冗长套话，控制在 150 字以内。
2. 严禁在回复中输出任何 emoji 符号。
3. 请以专业、得体、富有启发性的身份，使用整洁美观的 Markdown 格式为主人呈现解答。
```

---

## 5. 打包发送给 LLM API 的 Messages 格式

`LLMAgent` 最终组装的 HTTP 请求数据包格式（符合 OpenAI Chat Completions 规范）：

```json
{
  "model": "deepseek-chat",
  "messages": [
    {
      "role": "system",
      "content": "<Persona Prompt>\n\n【当前棋盘局面】\n- FEN: ...\n- 当前行动方: 白方\n- 合法走法数: 20\n- 完整 PGN 棋谱:\n```pgn\n...\n```\n\n【开局库推荐候选走法】: e4 (权重:100), d4 (权重:80)\n\n【Stockfish 引擎评估】\n- 候选 1: 评分 +25 cp, 主变例: e2e4 e7e5 g1f3"
    },
    {
      "role": "user",
      "content": "<PromptBuilder 生成的教学提示词 或 用户手动提问>"
    }
  ],
  "max_tokens": 1024,
  "temperature": 0.7,
  "stream": false
}
```

---

## 6. 女仆陪练对弈机制 (VS_MAID_LLM)

当对弈模式切换为 **女仆陪练 (vs Maid LLM)** 时：
1. `GameController` 异步调度 `EngineWorker(is_maid_llm=True)`。
2. Worker 调用 `LLMAgent.get_move(request)`。
3. Agent 向 LLM 发起精准单步走法请求（要求返回纯 UCI 格式着法如 `e7e5`）。
4. 解析成功后返回 UCI 着法；若 LLM 离线或解析异常，自动通过开局库/引擎/合法走法降级，确保对局永不卡顿。

