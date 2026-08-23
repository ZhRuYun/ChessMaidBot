# AGENTS.md - AI 协作与二次开发规范

> **【强制执行令】致所有阅读此文件的 AI 模型（包括但不限于 Claude, GPT, GLM, DeepSeek, Gemini 等）：**
> 当你以编码助手身份参与本项目（ChessMaidBot）的开发、修改或重构时，**必须严格遵守以下准则**。违背本准则可能导致系统架构腐化、状态不同步或引入隐蔽 Bug。

---

## 1. 架构红线（绝对禁止）

1. **禁止在 GUI 层直接修改棋局状态**：
   - 严禁在 `src/gui/` 下的任何组件中调用 `BoardState.make_move()`、`board.push()` 或直接修改记谱数据。
   - 所有走棋、悔棋、重开等状态变更必须通过发出信号交由 `GameController`（`src/controller/game_controller.py`）统一执行。
2. **禁止维护第二份记谱/状态数据源**：
   - 走法历史的唯一数据源是 `src/core/game_record.py` 中的 `MoveHistoryManager`。
   - GUI 面板（`MoveHistoryPanel`）仅负责被动接收 `records` 列表并调用 `set_records()` 进行整表渲染。
3. **禁止把二进制文件或运行期数据提交到 Git**：
   - `engines/` 目录下的引擎二进制、`data/games/` 目录下的 PGN 文件、`__pycache__` 等必须保持在 `.gitignore` 中，严禁强制提交。

---

## 2. 核心模块开发职责与规范

| 模块 | 路径 | 允许的操作 | 严格禁止的操作 |
|---|---|---|---|
| **GUI 界面** | `src/gui/` | 监听鼠标/键盘事件，发出意图信号（如 `move_ready`），接收控制器广播信号并刷新视图 | 编写规则判定逻辑、修改全局棋盘状态、直接操作数据库 |
| **调度层** | `src/controller/` | 统筹对弈模式、触发教学开关、调用规则核心执行走子、调用历史库归档、向 UI 广播信号 | 引入具体 UI 绘制逻辑、绕过接口直接操作底层原始数据 |
| **规则核心** | `src/core/` | 封装 `python-chess` 规则、解析易位/升变/吃过路兵、管理 FEN/PGN、维护被吃子堆栈 | 依赖 GUI 或 Controller 模块（core 必须是底层纯逻辑） |
| **引擎通信** | `src/engine/` | 维护与 Stockfish 的 UCI 协议交互、提供 `best_move` 和 `analyse` 方法 | 假定本地一定存在 Stockfish（必须具备无二进制时的降级容错机制） |
| **Agent 接口** | `src/agents/` | 实现 `ChessAgent` 接口，解析 `AgentRequest`，调用大模型并返回 Markdown 文本 | 直接操作棋盘或依赖 Qt 图形控件 |
| **数据库** | `src/database/` | 负责 `data/games/` 目录下的 PGN 读写，管理开局/战术/残局库文件 | 在保存失败时抛出未捕获异常导致程序崩溃 |

---

## 3. 修改源码后的强制任务（AI 必须执行）

当你受用户指示修改了本项目代码后，你必须完成以下闭环流程：

1. **运行全量测试**：
   ```bash
   QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
   ```
   - 必须确保所有现有测试用例 100% 通过（PASS）。
   - 如果新增了功能或类，必须在 `tests/` 目录下添加对应的单元测试。
2. **同步更新架构文档**：
   - 若新增了文件或模块，更新 `README.md` 的目录树。
   - 若调整了接口定义或通信协议，更新 `ARCHITECTURE.md` 中的接口规范与时序图。
3. **提交规范**：
   - 提交信息（Commit Message）需清晰简练，按模块标明修改内容（如 `feat(agent): 接入真实 LLM API 客户端`）。

---

## 4. 常见代码模式模板

### 新增 Agent 模板
```python
# 文件位置: src/agents/xxx_agent.py
from .base import ChessAgent, AgentRequest

class MyAgent(ChessAgent):
    name = "my_custom_agent"

    def reply(self, request: AgentRequest) -> str:
        # 1. 从 request.snapshot 获取当前局面信息
        # 2. 从 request.user_message 获取用户输入
        # 3. 从 request.persona_prompt 获取人设 Prompt
        # 4. 调用后端生成回复 (支持 Markdown 语法)
        return "回复内容"
```

### 调度层扩展模式模板
```python
# 当需要为控制器添加新能力时 (如引擎走棋):
# 在 GameController 中定义方法 -> 更新 BoardState -> emit 相应信号
```
