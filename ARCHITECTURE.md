# ChessMaidBot 架构设计与接口规范

> 本文档详细定义了 ChessMaidBot 六大模块的职责划分、数据流向、通信协议及扩展规范。所有参与本项目的开发者与 AI 模型必须严格遵循此规范。

---

## 目录
- [一、六大模块架构蓝图](#一六大模块架构蓝图)
- [二、模块详细设计与职责](#二模块详细设计与职责)
  - [模块 1: GUI 交互界面](#模块-1-gui-交互界面-srcgui)
  - [模块 2: Controller 调度中枢层](#模块-2-controller-调度中枢层-srccontroller)
  - [模块 3: 国际象棋规则核心](#模块-3-国际象棋规则核心-srccore)
  - [模块 4: Stockfish 引擎接口](#模块-4-stockfish-引擎接口-srcengine)
  - [模块 5: Agent 接口及方法库](#模块-5-agent-接口及方法库-srcagents)
  - [模块 6: 数据库与棋局持久化](#模块-6-数据库与棋局持久化-srcdatabase)
- [三、核心数据流向与时序](#三核心数据流向与时序)
- [四、未来功能扩展标准契约](#四未来功能扩展标准契约)

---

## 一、六大模块架构蓝图

```
                   ┌──────────────────────────────────────┐
                   │            用户交互 (UI)              │
                   └──────────────────┬───────────────────┘
                                      │
 ┌────────────────────────────────────▼────────────────────────────────────┐
 │ 模块 1: GUI 交互界面 (src/gui/)                                          │
 │  ├── ChessBoardWidget (纯绘制与事件捕获)                                   │
 │  ├── ChatPanel (LLM 对话展示与 5 级教学开关)                             │
 │  ├── MoveHistoryPanel (双栏记谱纯渲染表格)                               │
 │  ├── ControlBar (模式选择/控制按钮)                                      │
 │  └── PromotionDialog (升变选择框)                                       │
 └─────────────────▲──────────────────────────────┬────────────────────────┘
                   │ (信号监听与渲染刷新)             │ 仅发用户意图信号 (move_ready)
 ┌─────────────────┴──────────────────────────────▼────────────────────────┐
 │ 模块 2: Controller 调度中枢层 (src/controller/)                           │
 │  ├── GameController (棋局状态唯一写入口，统筹调度)                          │
 │  ├── GameModeManager (对弈模式状态机: 本地双人 / vs 引擎 / vs LLM)         │
 │  └── TeachingTriggers (教学触发器 5 级开关配置对象)                       │
 └───┬──────────────────────────┬─────────────────────────────┬────────────┘
     │ 规则调用与状态修改          │ UCI 通信与分析               │ 终局归档保存
 ┌───▼──────────────────┐   ┌───▼───────────────────────┐   ┌─▼────────────┐
 │ 模块 3: 规则核心       │   │ 模块 4: Stockfish 引擎     │   │ 模块 6: 数据库 │
 │ src/core/            │   │ src/engine/               │   │ src/database/│
 │ ├── BoardState       │   │ └── StockfishClient       │   │ └── History- │
 │ └── MoveHistory-     │   │     (UCI 通信/多PV评估)     │   │     Store    │
 │     Manager          │   └───────────┬───────────────┘   └──────────────┘
 └──────────────────────┘               │ (提供引擎分析数据)
                                ┌───────▼───────────────┐
                                │ 模块 5: Agent 接口     │
                                │ src/agents/           │
                                │ ├── ChessAgent (抽象)  │
                                │ ├── AgentRequest (包) │
                                │ └── EchoAgent/LLMAgent│
                                └───────────────────────┘
```

---

## 二、模块详细设计与职责

### 模块 1: GUI 交互界面 (`src/gui/`)
* **设计原则**：**瘦视图（Thin View）**。GUI 组件只负责画面渲染与鼠标/键盘事件捕获，严禁包含任何棋局走法逻辑或直接修改规则状态。
* **主要文件**：
  * `chess_board.py` (`ChessBoardWidget`): 基于 PySide6 + QSvgRenderer 矢量直绘，支持高清抗锯齿、拖拽和点击落子、Lichess 风格王车易位、将军红色高亮与上步高亮。捕获到合法落子后发送 `move_ready(chess.Move)` 信号。
  * `chat_panel.py` (`ChatPanel`): 包含女仆状态标头、5 级教学触发器复选框、Markdown 气泡流展示、快捷提问条及统一输入框。
  * `move_history_panel.py` (`MoveHistoryPanel`): 纯双栏记谱表格，通过 `set_records(records)` 方法整表重建渲染。
  * `control_bar.py` (`ControlBar`): 模式下拉列表、新对局、悔棋、翻转棋盘、导出 PGN/FEN 按钮。
  * `main_window.py` (`MainWindow`): 装配中心，负责将 Controller 的广播信号与各 GUI 面板的槽函数连接。

### 模块 2: Controller 调度中枢层 (`src/controller/`)
* **设计原则**：**棋局状态的唯一写路径**。所有落子、悔棋、新局、模式变更必须经由该层执行。
* **主要文件**：
  * `game_controller.py` (`GameController`):
    * 维护 `BoardState`、`MoveHistoryManager`、`GameModeManager`、`TeachingTriggers`、`HistoryStore`。
    * 提供 `apply_move()`, `undo()`, `new_game()`, `export_pgn()`, `import_pgn()` 等写接口。
    * 核心信号：`position_changed(last_move)`, `history_changed(records)`, `status_changed(text, in_check)`, `move_played(san, uci, is_white)`, `game_over(status)`, `game_reset()`, `mode_changed(mode)`。
  * `game_modes.py` (`GameModeManager`):
    * 枚举 `GameMode`: `LOCAL_PVP` (本地双人), `VS_ENGINE` (人机对弈), `VS_MAID_LLM` (女仆陪练)。
    * 管理引擎难度等级（Skill Level: 0 ~ 20）。
  * `teaching_triggers.py` (`TeachingTriggers`):
    * 数据结构：`master_enabled` (总开关), `eval_current_position` (当下局面评估), `suggest_moves` (建议着法), `eval_history_moves` (历史走法失误预警), `game_over_summary` (棋局结束总结)。

### 模块 3: 国际象棋规则核心 (`src/core/`)
* **设计原则**：基于 `python-chess` 封装的纯规则与状态管理。
* **主要文件**：
  * `board_state.py` (`BoardState`):
    * 维护底层 `chess.Board`、吃子堆栈 `captured_pieces`、PGN Header 字典。
    * 智能解析 Lichess 风格王车易位（点王再点车）及标准易位。
    * 严格管理合法性校验与走法执行（`make_move`, `undo_move`）。
    * 提供无损 `export_pgn()` 与带回滚机制的 `import_pgn()`。
  * `game_record.py` (`MoveHistoryManager`):
    * 管理 `MoveRecord`（包含步数、白方 SAN、黑方 SAN、走后各自的 FEN 快照）。
    * 完美支持黑先开局（首行白方记谱为 `...`）的追加与悔棋弹出。

### 模块 4: Stockfish 引擎接口 (`src/engine/`)
* **设计原则**：封装标准输入输出（stdin/stdout）的 UCI 异步/同步进程通信。
* **主要文件**：
  * `stockfish_client.py` (`StockfishClient`):
    * 自动探测 `engines/stockfish` 可执行文件。
    * 提供 `start()`, `quit()`, `set_skill_level(level: 0~20)`。
    * `best_move(fen, movetime_ms)`: 计算最佳单步走法。
    * `analyse(fen, depth, multipv)`: 返回多 PV 分析结果列表（包含评分 `score_cp` 与着法主变例 `pv`）。

### 模块 5: Agent 接口及方法库 (`src/agents/`)
* **设计原则**：面向 LLM 对话的抽象与标准化上下文打包。
* **主要文件**：
  * `base.py`:
    * `PositionSnapshot`: 纯数据类，打包 FEN、PGN、当前行棋方、合法走法数、将军状态、终局原因。
    * `AgentRequest`: 发给大模型的标准请求体（`user_message` + `persona_prompt` + `snapshot` + `dialog_history`）。
    * `ChessAgent`: 抽象基类，定义 `reply(self, request: AgentRequest) -> str`。
  * `echo_agent.py` (`EchoAgent`): 本地回声代理，用于无 LLM API 时的开发测试与链路占位。

### 模块 6: 数据库与棋局持久化 (`src/database/`)
* **设计原则**：轻量文本持久化，优先面向 LLM 可读格式（PGN）。
* **主要文件**：
  * `history_store.py` (`HistoryStore`):
    * 存储根目录 `data/games/`。
    * 对局终局时自动以 `YYYYMMDD-HHMMSS-结果.pgn` 格式归档。
    * 预留开局库 (ECO/Polyglot)、EPD 战术库、残局库接入点。

---

## 三、核心数据流向与时序

```
[玩家在棋盘上移动棋子]
        │
        ▼
1. ChessBoardWidget 
   └─► resolve_castling_or_normal_move() 校验
   └─► 触发升变对话框 (如适用)
   └─► emit move_ready(chess.Move)
        │
        ▼
2. GameController.apply_move(move)
   ├─► BoardState.make_move(move)
   ├─► MoveHistoryManager.add_move(san, is_white, fen)
   ├─► emit position_changed / history_changed / status_changed
   ├─► 判定终局:
   │    └─► 若 Game Over ──► HistoryStore.save_game(pgn, result) ──► emit game_over(status)
   └─► emit move_played(san, uci, was_white)
        │
        ▼
3. MainWindow (UI 响应)
   ├─► ChessBoardWidget.show_move(last_move) (高亮与重绘)
   ├─► MoveHistoryPanel.set_records(records) (整表刷新)
   └─► on_move_played: 若处于将军且教学开关开启 ──► 调用 Agent 生成提醒消息 ──► ChatPanel 气泡展示
```

---

## 四、未来功能扩展标准契约

### 1. 接入真实大语言模型 (LLM)
* **创建位置**：`src/agents/openai_agent.py` 或 `src/agents/deepseek_agent.py`
* **实现方式**：
  ```python
  from src.agents.base import ChessAgent, AgentRequest

  class DeepSeekMaidAgent(ChessAgent):
      def __init__(self, api_key: str, base_url: str):
          self.api_key = api_key
          # 初始化 API 客户端...

      def reply(self, request: AgentRequest) -> str:
          system_prompt = request.persona_prompt
          user_content = (
              f"【对局状态】\n"
              f"FEN: {request.snapshot.fen}\n"
              f"行动方: {request.snapshot.turn}\n"
              f"是否将军: {request.snapshot.in_check}\n\n"
              f"【玩家提问】\n{request.user_message}"
          )
          # 调用 API 获取返回文本 (Markdown 格式)
          return response_text
  ```
* **注入方式**：在 `main.py` 启动时直接实例化并注入 `MainWindow(agent=DeepSeekMaidAgent(...))`。

### 2. 接入人机对弈与引擎自动走棋
* **触发机制**：在 `GameController.move_played` 信号响应中，检测当前模式是否为 `GameMode.VS_ENGINE` 且当前轮到引擎方：
  ```python
  if self.modes.mode == GameMode.VS_ENGINE and self.board_state.turn == chess.BLACK:
      with StockfishClient() as engine:
          engine.set_skill_level(self.modes.engine_skill)
          uci_move = engine.best_move(self.board_state.get_fen(), movetime_ms=800)
          if uci_move:
              self.apply_move(chess.Move.from_uci(uci_move))
  ```

### 3. 接入树形变例分析
* **数据契约**：`MoveRecord` 中的 `fen_after_white` 与 `fen_after_black` 已为每步提供了完整局面快照。
* **实现逻辑**：当用户在记谱表点击历史某一步并走棋时，读取该记录的 FEN，通过 `GameController.new_game(fen=selected_fen)` 即可无缝创建平行分支对局。
