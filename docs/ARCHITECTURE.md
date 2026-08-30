# ChessMaidBot 架构设计与接口规范

> 本文档详细定义了 ChessMaidBot 六大模块的职责划分、数据流向、通信协议及扩展规范。所有参与本项目的开发者与 AI 模型必须严格遵循此规范。

---

## 目录
- [一、六大模块架构蓝图](#一六大模块架构蓝图)
- [二、设计功能完成度一览（已完成 vs 尚未完成）](#二设计功能完成度一览已完成-vs-尚未完成)
- [三、模块详细设计与职责](#三模块详细设计与职责)
  - [模块 1: GUI 交互界面](#模块-1-gui-交互界面-srcgui)
  - [模块 2: Controller 调度中枢层](#模块-2-controller-调度中枢层-srccontroller)
  - [模块 3: 国际象棋规则核心](#模块-3-国际象棋规则核心-srccore)
  - [模块 4: Stockfish 引擎接口](#模块-4-stockfish-引擎接口-srcengine)
  - [模块 5: Agent 接口及方法库](#模块-5-agent-接口及方法库-srcagents)
  - [模块 6: 数据库与棋局持久化](#模块-6-数据库与棋局持久化-srcdatabase)
- [四、核心数据流向与时序](#四核心数据流向与时序)
- [五、未来功能扩展标准契约](#五未来功能扩展标准契约)

---

## 一、六大模块架构蓝图

```
                   ┌────────────────────────────────────────────────────────┐
                   │                  用户交互操作 (UI)                     │
                   └─────────────────────────┬──────────────────────────────┘
                                             │
 ┌───────────────────────────────────────────▼───────────────────────────────────────────┐
 │ 模块 1: GUI 交互界面 (src/gui/)                                                         │
 │  ├── MoveHistoryPanel (左侧: 双栏记谱纯渲染表格)                                        │
 │  ├── ChessBoardWidget (中央: 纯绘制与事件捕获)                                         │
 │  ├── ChatPanel (右侧: LLM 对话展示, 主动询问LLM 与 LoadingSpinner 转圈)                 │
 │  ├── ControlBar (顶部: 模式选择 / Elo 调节 / 认输 / 求和 / 导出棋局状态(PGN+FEN))       │
 │  ├── LoadingSpinner (现代极简平滑旋转指示器)                                            │
 │  └── PromotionDialog (升变选择框)                                                      │
 └─────────────────▲───────────────────────────────────────┬──────────────────────────────┘
                   │ (信号监听与渲染刷新)                      │ 仅发用户意图 (move_ready / resign / draw)
 ┌─────────────────┴───────────────────────────────────────▼──────────────────────────────┐
 │ 模块 2: Controller 调度中枢层 (src/controller/)                                          │
  │  ├── GameController (棋局状态唯一写入口，统筹人机/本地对弈、认输求和、归档)             │
  │  ├── EngineWorker (QThread 后台异步计算引擎着法，避免 UI 阻塞)                           │
  │  ├── GameModeManager (对弈模式状态机与 Elo 评分管理)                                    │
  │  └── TeachingTriggers (教学触发器 5 级开关配置对象)                                    │
 └───┬──────────────────────────┬─────────────────────────────┬───────────────────────────┘
     │ 规则调用与状态修改          │ UCI 目标 Elo 通信与分析      │ 终局归档 (PGN+LLM总结)
 ┌───▼──────────────────┐   ┌───▼───────────────────────┐   ┌─▼───────────────────────────┐
 │ 模块 3: 规则核心       │   │ 模块 4: Stockfish 引擎     │   │ 模块 6: 数据库与持久化      │
 │ src/core/            │   │ src/engine/               │   │ src/database/               │
 │ ├── BoardState       │   │ └── StockfishClient       │   │ └── HistoryStore            │
 │ └── MoveHistory-     │   │     (UCI_Elo / 多PV评估)  │   │     (PGN+LLM复合结构/多库)  │
 │     Manager          │   └───────────┬───────────────┘   └─────────────────────────────┘
 └──────────────────────┘               │ (提供引擎分析数据与工具集)
                                 ┌───────▼───────────────┐
                                 │ 模块 5: Agent 接口     │
                                 │ src/agents/           │
                                 │ ├── ChessAgent (抽象)  │
                                 │ ├── AgentTools (方法库)│
                                 │ ├── AgentRequest (包) │
                                 │ ├── PromptBuilder     │
                                 │ └── EchoAgent/LLMAgent│
                                 └───────────────────────┘
```

---

## 二、设计功能完成度一览（已完成 vs 尚未完成）

### ✅ 已完成的设计功能
1. **模块 1: GUI 交互界面**
   - 居中自研矢量高清直绘棋盘（抗锯齿、拖拽/点击、王车易位、升变选择、将军高亮）。
   - 左侧纯双栏记谱表格（被动响应式整表重建，单一数据源，浅色/深色主题完整适配）。
   - 右侧 LLM 聊天面板（Markdown 气泡渲染、快捷提问条、LoadingSpinner 状态徽章）。
   - 顶部控制栏（模式下拉切换、Stockfish 目标 Elo 微调、新局、悔棋、翻转、认输、求和、PGN/FEN 导出、浅色/深色主题）。
2. **模块 2: Controller 调度中枢层**
   - 棋局状态唯一写入口（`apply_move`, `undo`, `resign`, `offer_draw`, `accept_draw`, `new_game`）。
   - 人机对弈调度机与 `EngineWorker`（`QThread`）后台异步计算线程（维持 UI 响应）。
   - 对弈模式管理器（扮演双方棋手、人机对弈、女仆陪练与网络双人对战原型，支持执黑/执白自由选边）。
   - 教学触发器总开关与 4 级细分开关状态管理。
3. **模块 3: 国际象棋规则核心**
   - `BoardState` 规则封装（合法性校验、吃过路兵、被吃子堆栈、防越界回滚）。
   - `MoveHistoryManager` 双栏记谱与黑先开局占位记谱支持。
   - PGN / FEN 标准编解码与无损导入导出。
4. **模块 4: Stockfish 引擎调度**
   - `StockfishClient` 命令行 UCI 通信封装与容错降级。
   - 通过官方 UCI 选项（`UCI_LimitStrength` + `UCI_Elo`）精确控制目标 Elo（500 ~ 3190）。
   - 多 PV（MultiPV）深度着法打分与最佳单步计算。
   - 统一引擎状态查询接口 `get_state`。
5. **模块 5: Agent 接口与方法库**
   - 自定义 LLM 人设 Prompt 注入机制与持久化保存（`data/settings.json`）。
   - 标准化上下文请求包 `AgentRequest`（打包 FEN、PGN、行动方、游戏模式、快照与人设）。
   - 为 LLM 提供方法库接口 `AgentTools`（数据库读取、Stockfish 状态读取、联网搜索工具等）。
6. **模块 6: 数据库与棋局持久化**
   - 终局以“标准 PGN + LLM 对局总结”复合结构持久化至 `data/games/`。
   - 复合棋谱文件解析方法 `parse_game_file`。
   - `OpeningBook`：支持来自 Lichess 开源库 (`data/books/openings.json`) 与可选 Polyglot (.bin) 的开局名称识别及推荐走法。
   - `HistoryStore`：保存正常结束的玩家历史棋局及 LLM 总结。
   - 统一数据库查询接口 `query_database`（提供 history / opening 统一分发）。
   - 配套一键初始化安装脚本 `scripts/download_assets.py`。

### 💡 项目功能完成状态
本系统核心功能（六大模块：GUI三栏交互、调度中枢、规则核心、Stockfish 引擎调度、LLM Agent 接口与方法库、统一数据库与复合棋谱归档、网络双人对战及搜索 API 配置）均已全面实装并稳定通过测试。

---

## 三、模块详细设计与职责

### 模块 1: GUI 交互界面 (`src/gui/`)
* **设计原则**：**瘦视图（Thin View）** 与 **三栏布局（左:记谱表, 中:棋盘, 右:LLM聊天）**。
* **主要文件**：
  * `chess_board.py` (`ChessBoardWidget`): 居中展示。基于 PySide6 + QSvgRenderer 矢量直绘，支持抗锯齿、拖拽和点击落子、Lichess 风格王车易位、将军红色高亮。捕获合法落子后发送 `move_ready(chess.Move)` 信号。
  * `move_history_panel.py` (`MoveHistoryPanel`): 布局在左侧。纯双栏记谱表格，通过 `set_records(records)` 方法整表重建渲染。
   * `chat_panel.py` (`ChatPanel`): 布局在右侧。包含女仆状态标头、LoadingSpinner 转圈动效、Markdown 气泡流展示、“✨ 主动询问女仆指导” 按钮及统一输入框。
   * `control_bar.py` (`ControlBar`): 顶部控制条。包含模式下拉列表、Stockfish 目标 Elo 微调框（500~3190）、新对局、悔棋、翻转棋盘、🤝 求和、🏳️ 认输、📋 导出棋局状态 (PGN+FEN 一键复制到剪贴板) 按钮。
   * `loading_spinner.py` (`LoadingSpinner`): 现代极简圆形旋转平滑加载控件。
   * `main_window.py` (`MainWindow`): 装配中心，负责将 Controller 的广播信号与各 GUI 面板的槽函数连接，并管理 `LLMWorker` 后台异步响应。

### 模块 2: Controller 调度中枢层 (`src/controller/`)
* **设计原则**：**棋局状态的唯一写路径**。所有落子、悔棋、认输、求和、人机异步触发必须经由该层执行。
* **主要文件**：
  * `game_controller.py` (`GameController`, `EngineWorker`):
    * 维护 `BoardState`、`MoveHistoryManager`、`GameModeManager`、`TeachingTriggers`、`HistoryStore`。
    * 提供 `apply_move()`, `undo()`, `resign()`, `offer_draw()`, `accept_draw()`, `new_game()`, `export_pgn()`, `import_pgn()` 等写接口。
    * 启动 `EngineWorker` 子线程异步计算引擎走法（经 `shared_engine` 共享进程串行执行），计算完成后自动投递 `apply_move`，并在思考期间通过 `engine_thinking_changed` 锁定棋盘。
    * 过期异步结果通过「代际 (generation) 丢弃」机制失效（重开/悔棋/换边时自增代际号），不使用 `terminate()` 强杀线程，杜绝共享引擎死锁与 UCI 协议失步。
    * 在终局时组合 `export_pgn()` 与 LLM 总结回调，于后台守护线程生成复合文件写入数据库（LLM 复盘网络请求不阻塞 UI）。
  * `game_modes.py` (`GameModeManager`):
    * 枚举 `GameMode`: `LOCAL_PVP` (本地双人), `VS_ENGINE` (人机对弈), `VS_MAID_LLM` (女仆陪练)。
    * 管理引擎强度模式（`use_elo` 开关，目标 Elo: 500 ~ 3190，Skill Level: 0 ~ 20）。
  * `teaching_triggers.py` (`TeachingTriggers`):
    * 数据结构：`master_enabled` (总开关), `eval_current_position` (当下局面评估), `suggest_moves` (建议着法), `eval_history_moves` (历史走法失误预警), `game_over_summary` (棋局结束总结)。

### 模块 3: 国际象棋规则核心 (`src/core/`)
* **设计原则**：基于 `python-chess` 封装的纯规则与状态管理。
* **主要文件**：
  * `board_state.py` (`BoardState`):
    * 维护底层 `chess.Board`、吃子堆栈 `captured_pieces`、PGN Header 字典。
    * 智能解析 Lichess 风格王车易位（点王再点车）及标准易位。
    * 严格管理合法性校验与走法执行（`make_move`, `undo_move`）。
    * 提供无损 `export_pgn(override_result)` 与带回滚机制的 `import_pgn()`。
  * `game_record.py` (`MoveHistoryManager`):
    * 管理 `MoveRecord`（包含步数、白方 SAN、黑方 SAN、走后各自的 FEN 快照）。
    * 完美支持黑先开局（首行白方记谱为 `...`）的追加与悔棋弹出。

### 模块 4: Stockfish 引擎接口 (`src/engine/`)
* **设计原则**：封装标准输入输出（stdin/stdout）的 UCI 异步/同步进程通信。
* **主要文件**：
  * `stockfish_client.py` (`StockfishClient`, `SharedEngine` / `shared_engine`):
    * 自动探测 `engines/stockfish` 可执行文件。
    * 提供 `start()`, `quit()`, `set_skill_level(level: 0~20)`。
    * 提供 `set_elo(elo: 500~3190)`：通过 UCI 选项 `UCI_LimitStrength` 与 `UCI_Elo` 精准控制目标 Elo。
    * `best_move(fen, movetime_ms)`: 计算最佳单步走法。
    * `analyse(fen, depth, multipv)`: 返回多 PV 分析结果列表（包含评分 `score_cp` 与着法主变例 `pv`）。
    * `get_state(fen, state_type, **kwargs)`: 为 Agent 与上层模块提供统一引擎状态查询接口。
    * `SharedEngine` / `shared_engine`：进程级共享引擎客户端池（懒启动 + 线程互斥复用），供 `EngineWorker`、求和评估与 Agent 工具统一复用同一 Stockfish 子进程，避免每次调用重复拉起进程与加载 NNUE 权重的开销；异常时自动销毁并重建客户端。

### 模块 5: Agent 接口及方法库 (`src/agents/`)
* **设计原则**：面向 LLM 对话的抽象与标准化上下文打包。
* **主要文件**：
  * `base.py`:
    * `PositionSnapshot`: 纯数据类，打包 FEN、PGN、当前行棋方、合法走法数、将军状态、终局原因。
    * `AgentTools`: 提供给 LLM 的方法库契约（数据库读取、Stockfish 状态读取等 4 类能力）。
    * `AgentRequest`: 发给大模型的标准请求体（`user_message` + `persona_prompt` + `snapshot` + `dialog_history` + `tools`）。
    * `ChessAgent`: 抽象基类，定义 `reply(self, request: AgentRequest) -> str`。
  * `prompt_builder.py` (`PromptBuilder`):
    * 依据棋盘现状（PGN、FEN、行动方、最近走法）及 4 个教学细分开关生成定制化 Prompt，支持每步自动教学与主动询问定制。
  * `echo_agent.py` (`EchoAgent`): 本地回声代理，用于无 LLM API 时的开发测试与链路占位。

### 模块 6: 数据库与棋局持久化 (`src/database/`)
* **设计原则**：面向 LLM 纯文本设计的“标准 PGN + LLM 对局总结”复合结构持久化，以及开局库与历史库在 `data/` 大目录下的解耦与统一分发。
* **主要文件**：
  * `unified_db.py` (`UnifiedDatabase`): 统一数据库聚合入口，统筹管理 `data/` 大目录下的子库。
  * `history_store.py` (`HistoryStore`):
    * 存储根目录 `data/games/`。
    * 仅在玩家正常完赛（将死、被将死、认输、协议和棋等）时以 `YYYYMMDD-HHMMSS-结果.pgn` 格式归档，并在文件末尾追加 `% --- LLM GAME SUMMARY ---` 总结区。
    * 内置 `is_useful_game(pgn_text, result)` 与 `list_games(filter_useless=True)` 过滤机制，排除未开局即认输/求和或未完赛的无用棋局。
    * 提供 `parse_game_file(content)` 分离 PGN 与总结文本。
    * 统筹 `OpeningBook`，提供统一的 `query_database(category, **kwargs)` 接口。
  * `opening_book.py` (`OpeningBook`):
    * 位于 `data/books/`。基于 Lichess 开源开局库 (`data/books/openings.json`) 与 ECO 体系识别开局名称，并支持候选走法及权重推荐。

---

## 四、核心数据流向与时序

### 1. 玩家下棋与人机对弈走棋流程
```
[玩家在中央棋盘操作]
        │
        ▼
1. ChessBoardWidget ──► emit move_ready(chess.Move)
        │
        ▼
2. GameController.apply_move(move)
   ├─► BoardState.make_move(move)
   ├─► MoveHistoryManager.add_move(san, is_white, fen)
   ├─► emit position_changed / history_changed / status_changed
   ├─► 判定是否人机对弈模式 (GameMode.VS_ENGINE 且轮到黑方):
   │    └─► 启动 EngineWorker(QThread)
   │         └─► StockfishClient.best_move() ──► emit move_computed(uci) ──► GameController.apply_move()
   └─► 判定终局:
        └─► 若 Game Over ──► 生成 LLM 总结 ──► HistoryStore.save_game(pgn, result, summary) ──► emit game_over
```

---

## 五、未来功能扩展标准契约

### 1. 接入与扩展真实大语言模型 (LLM)
在子类中实现 `reply(self, request: AgentRequest) -> str`，支持配置 `reasoning_effort` 与 `stream` 模式，并可在内部调用 `request.tools.read_engine_state()` 或 `request.tools.read_database()`。
