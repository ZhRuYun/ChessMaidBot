# ChessMaidBot 架构设计与接口规范

> 本文档详细定义了 ChessMaidBot 六大模块的职责划分、数据流向、通信协议、异步线程模型与扩展规范。所有参与本项目的开发者与 AI 协作模型必须严格遵循此规范。

---

## 目录
- [一、六大模块架构蓝图](#一六大模块架构蓝图)
- [二、设计功能完成度一览](#二设计功能完成度一览)
- [三、模块详细设计与职责](#三模块详细设计与职责)
  - [模块 1: GUI 交互界面 (src/gui/)](#模块-1-gui-交互界面-srcgui)
  - [模块 2: Controller 调度中枢层 (src/controller/)](#模块-2-controller-调度中枢层-srccontroller)
  - [模块 3: 国际象棋规则核心 (src/core/)](#模块-3-国际象棋规则核心-srccore)
  - [模块 4: Stockfish 引擎调度 (src/engine/)](#模块-4-stockfish-引擎调度-srcengine)
  - [模块 5: Agent 接口与记忆层 (src/agents/)](#模块-5-agent-接口与记忆层-srcagents)
  - [模块 6: 数据库与棋局持久化 (src/database/)](#模块-6-数据库与棋局持久化-srcdatabase)
- [四、核心数据流向与异步时序](#四核心数据流向与异步时序)
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
 │  ├── MoveHistoryPanel (左侧: 双栏记谱纯渲染表格 + 步数导航)                             │
 │  ├── ChessBoardWidget (中央: 矢量直绘棋盘 + 点击/拖拽 + 预览模式)                       │
 │  ├── ChatPanel (右侧: LLM 流式对话展示, 主动提问, LoadingSpinner 动画)                 │
 │  ├── ControlBar (顶部: 模式选择 / Elo 微调 / 认输 / 求和 / PGN+FEN 导入导出 / 主题切换) │
 │  └── LLMConfigDialog & PersonaConfigDialog (AI 与人设综合配置)                         │
 └─────────────────▲───────────────────────────────────────┬──────────────────────────────┘
                   │ (信号监听与渲染刷新)                      │ 仅发用户意图 (move_ready / resign / draw)
 ┌─────────────────┴───────────────────────────────────────▼──────────────────────────────┐
 │ 模块 2: Controller 调度中枢层 (src/controller/)                                          │
 │  ├── GameController (棋局状态唯一写入口，统筹多模式对弈、Coach 评估、终局归档)         │
 │  ├── EngineWorker (QThread 后台异步走子线程，代际丢弃机制)                             │
 │  ├── GameModeManager (对弈模式状态机与 Elo 控制)                                       │
 │  ├── TeachingTriggers (教学触发器 5 级开关管理)                                        │
 │  └── OnlineMatch (嵌入式网络对战服务与客户端)                                           │
 └───┬──────────────────────────┬─────────────────────────────┬───────────────────────────┘
     │ 规则调用与状态修改          │ UCI 目标 Elo 通信与分析      │ 终局归档 (PGN+LLM总结)
 ┌───▼──────────────────┐   ┌───▼───────────────────────┐   ┌─▼───────────────────────────┐
 │ 模块 3: 规则核心       │   │ 模块 4: Stockfish 引擎     │   │ 模块 6: 数据库与持久化      │
 │ src/core/            │   │ src/engine/               │   │ src/database/               │
 │ ├── BoardState       │   │ ├── StockfishClient       │   │ ├── HistoryStore            │
 │ └── MoveHistory-     │   │ └── SharedEngine          │   │ ├── OpeningBook             │
 │     Manager          │   │     (共享引擎池)          │   │ └── UnifiedDatabase         │
 └──────────────────────┘   └───────────┬───────────────┘   └─────────────────────────────┘
                                        │ (提供引擎分析数据与工具集)
                                ┌───────▼───────────────┐
                                │ 模块 5: Agent 与记忆   │
                                │ src/agents/           │
                                │ ├── LLMAgent (结构化) │
                                │ ├── ShortTermMemory   │
                                │ ├── LongTermMemory    │
                                │ ├── MultiRole (教练)  │
                                │ └── PromptBuilder     │
                                └───────────────────────┘
```

---

## 二、设计功能完成度一览

### ✅ 已全面实装功能
1. **模块 1: GUI 交互界面**
   - 居中自研矢量高清抗锯齿棋盘（支持拖拽/点击、Lichess 风格王车易位、升变选择、将军红色警示）。
   - 左侧双栏记谱表（响应式整表重建，支持首步、前一步、后一步、最后一步历史步数点击即时预览）。
   - 右侧 LLM 聊天面板（Markdown 气泡渲染、流式打字机逐字输出、LoadingSpinner 思考指示器）。
   - 顶部控制栏（模式下拉、目标 Elo 调节框、新局、悔棋、翻转、认输、求和、PGN/FEN 导入导出、主题切换）。
   - 综合 AI 配置与人设模板管理（支持 API Base、Key、模型拉取、思考档位、流式开关、搜索接口配置）。
2. **模块 2: Controller 调度中枢层**
   - 棋局状态唯一写入口（`apply_move`, `undo`, `resign`, `offer_draw`, `accept_draw`, `new_game`）。
   - 人机对弈调度机与 `EngineWorker`（`QThread`）后台异步计算线程，代际号（Generation）丢弃机制防悬挂。
   - 对弈模式管理器（本地双人、人机对弈、女仆陪练、网络对战），支持执黑/执白选边。
   - 教学触发器总开关与 4 级细分开关状态管理。
   - Coach Mode 全盘着法质量自动化评估（$\Delta \text{cp}$ 打标 Best/Excellent/Good/Inaccuracy/Mistake/Blunder）。
3. **模块 3: 国际象棋规则核心**
   - `BoardState` 规则封装（合法性校验、吃过路兵、被吃子堆栈、防越界回滚）。
   - `MoveHistoryManager` 双栏记谱与黑先开局占位记谱支持。
   - PGN / FEN 标准编解码与无损导入导出。
4. **模块 4: Stockfish 引擎调度**
   - `StockfishClient` 命令行 UCI 通信封装与容错降级。
   - 通过官方 UCI 选项（`UCI_LimitStrength` + `UCI_Elo`）精确控制目标 Elo（500 ~ 3190）。
   - 多 PV（MultiPV）深度着法打分与最佳单步计算。
   - `SharedEngine` 进程级互斥复用池，杜绝频繁拉起子进程开销。
5. **模块 5: Agent 接口与记忆层**
   - `LLMAgent` 结构化输出（`json_object`）与 Schema 校验，彻底解决正则提取失误。
   - 双层记忆机制：`ShortTermMemory`（滑动窗口多轮对话）+ `LongTermMemory`（玩家画像与偏好持久化）。
   - 弹性传输与流式自愈解析器（`ResilientStreamParser`）。
   - 自主 Tool Calling（开局库、历史库、引擎深度分析、联网搜索与悔棋请求）。
   - 多角色协同解耦（`CoachRole` 棋理分析 + `MaidPersonaRole` 情感润色）。
6. **模块 6: 数据库与棋局持久化**
   - 终局以“标准 PGN + LLM 对局总结”复合结构持久化至 `data/games/`。
   - `OpeningBook`：支持来自 Lichess 开源库 (`data/books/openings.json`) 与可选 Polyglot (.bin) 的开局名称识别及推荐走法。
   - `HistoryStore`：保存正常结束的玩家历史棋局及 LLM 总结，内置有效性过滤器。
   - 统一数据库查询接口 `query_database`（提供 history / opening 统一分发）。

---

## 三、模块详细设计与职责

### 模块 1: GUI 交互界面 (`src/gui/`)
* **设计原则**：**瘦视图（Thin View）** 与 **响应式三栏布局**。
* **主要文件**：
  * `chess_board.py` (`ChessBoardWidget`): 居中展示。基于 PySide6 + QSvgRenderer 矢量直绘，支持抗锯齿、拖拽和点击落子、Lichess 风格王车易位、将军红色高亮。支持通过 `set_preview_board` 进入历史步数无损预览。
  * `move_history_panel.py` (`MoveHistoryPanel`): 布局在左侧。纯双栏记谱表格，支持步数高亮与导航控制。
  * `chat_panel.py` (`ChatPanel`): 布局在右侧。包含女仆状态标头、LoadingSpinner 转圈动效、Markdown 气泡流展示、“✨ 主动询问女仆指导” 按钮、流式追加及统一输入框。
  * `control_bar.py` (`ControlBar`): 顶部控制条。包含模式下拉列表、Stockfish 目标 Elo 微调框（500~3190）、新对局、悔棋、翻转棋盘、求和、认输、导出/导入按钮。
  * `loading_spinner.py` (`LoadingSpinner`): 现代极简平滑旋转加载控件。
  * `main_window.py` (`MainWindow`): 装配中心，负责信号与槽绑定、双层记忆调度与异步任务取消控制。

### 模块 2: Controller 调度中枢层 (`src/controller/`)
* **设计原则**：**棋局状态的唯一写路径**。所有落子、悔棋、认输、求和、人机异步触发必须经由该层执行。
* **主要文件**：
  * `game_controller.py` (`GameController`, `EngineWorker`):
    * 维护 `BoardState`、`MoveHistoryManager`、`GameModeManager`、`TeachingTriggers`、`HistoryStore`。
    * 提供 `apply_move()`, `undo()`, `resign()`, `offer_draw()`, `accept_draw()`, `new_game()`, `export_pgn()`, `import_pgn()` 等写接口。
    * 启动 `EngineWorker` 子线程异步计算引擎走法（经 `shared_engine` 共享进程串行执行）。
    * 过期异步结果通过「代际 (generation) 丢弃」机制失效，杜绝共享引擎死锁与协议失步。
    * `evaluate_game_moves_quality(depth=8)`: Coach Mode 全盘评估，计算每步走法 $\Delta \text{cp}$ 落差并打标。
    * 终局在后台守护线程生成复合文件写入数据库，避免 LLM 复盘网络请求卡顿 UI。
  * `game_modes.py` (`GameModeManager`):
    * 枚举 `GameMode`: `LOCAL_PVP` (本地双人), `VS_ENGINE` (人机对弈), `VS_MAID_LLM` (女仆陪练), `ONLINE_PVP` (网络双人对战)。
  * `teaching_triggers.py` (`TeachingTriggers`):
    * 数据结构：`master_enabled` (总开关), `eval_current_position`, `suggest_moves`, `eval_history_moves`, `game_over_summary`。
  * `online_match.py` (`EmbeddedOnlineServer`, `OnlineMatchClient`):
    * 内置基于 WebSocket 的全双工网络对战轻量服务与客户端。

### 模块 3: 国际象棋规则核心 (`src/core/`)
* **设计原则**：基于 `python-chess` 封装的纯规则与状态管理。
* **主要文件**：
  * `board_state.py` (`BoardState`):
    * 维护底层 `chess.Board`、吃子堆栈 `captured_pieces`、PGN Header 字典。
    * 严格管理合法性校验与走法执行（`make_move`, `undo_move`）。
    * 提供无损 `export_pgn(override_result)` 与带回滚机制的 `import_pgn()`。
  * `game_record.py` (`MoveHistoryManager`):
    * 管理 `MoveRecord`（包含步数、白方 SAN、黑方 SAN、走后各自的 FEN 快照与着法质量评估标记）。

### 模块 4: Stockfish 引擎接口 (`src/engine/`)
* **设计原则**：封装标准输入输出（stdin/stdout）的 UCI 异步/同步进程通信。
* **主要文件**：
  * `stockfish_client.py` (`StockfishClient`, `SharedEngine` / `shared_engine`):
    * 自动探测 `engines/stockfish` 可执行文件。
    * 提供 `set_elo(elo: 500~3190)`：通过 UCI 选项 `UCI_LimitStrength` 与 `UCI_Elo` 精准控制目标 Elo。
    * `best_move(fen, movetime_ms)` 与 `analyse(fen, depth, multipv)`。
    * `SharedEngine`：进程级共享引擎客户端池（懒启动 + 线程互斥复用），供后台计算、求和评估与 Agent 工具复用同一进程。

### 模块 5: Agent 接口及记忆层 (`src/agents/`)
* **设计原则**：面向 LLM 的标准化请求、双层记忆系统与结构化决策。
* **主要文件**：
  * `base.py`:
    * `PositionSnapshot`: 纯数据类，打包 FEN、PGN、当前行棋方、合法走法数、将军状态、终局原因。
    * `AgentTools`: 注入 5 大工具接口（开局库、历史库、引擎分析、联网搜索、悔棋申请）。
    * `AgentRequest`: 发给大模型的标准请求体（`user_message` + `persona_prompt` + `snapshot` + `dialog_history` + `tools`）。
  * `llm_agent.py` (`LLMAgent`, `ResilientStreamParser`):
    * 支持 OpenAI 兼容规范、思考档位与流式打字机回调。
    * `get_move`: 结构化 JSON Schema 输出与合法性过滤，彻底消除正则解析缺陷。
  * `memory.py` (`ShortTermMemory`, `LongTermMemory`, `PlayerProfile`):
    * `ShortTermMemory`: 维护最近对局滑动窗口对话历史。
    * `LongTermMemory`: 跨对局持久化玩家胜率、偏好开局、高频失误与棋风标签（`data/player_profile.json`）。
  * `multi_role.py` (`CoachRole`, `MaidPersonaRole`):
    * 多角色协同解耦编排。
  * `prompt_builder.py` (`PromptBuilder`):
    * 教学 Prompt 组装器，内置 `<!-- BEGIN_TRUSTED_CHESS_DATA -->` 防注入护栏。

### 模块 6: 数据库与棋局持久化 (`src/database/`)
* **设计原则**：“标准 PGN + LLM 对局总结”复合结构持久化与开局库解耦。
* **主要文件**：
  * `history_store.py` (`HistoryStore`):
    * 存储根目录 `data/games/`。
    * 仅在玩家正常完赛时以 `YYYYMMDD-HHMMSS-结果.pgn` 格式归档，文件末尾追加 `% --- LLM GAME SUMMARY ---` 总结区。
    * 提供 `parse_game_file(content)` 分离 PGN 与总结文本。
  * `opening_book.py` (`OpeningBook`):
    * 位于 `data/books/`。基于 Lichess 开源开局库 (`data/books/openings.json`) 与 ECO 体系识别开局名称与权重推荐。

---

## 四、核心数据流向与异步时序

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
   ├─► 判定对弈模式:
   │    ├─► 若 GameMode.VS_ENGINE 且轮到 AI:
   │    │    └─► 启动 EngineWorker(QThread) ──► StockfishClient.best_move() ──► apply_move()
   │    └─► 若 GameMode.VS_MAID_LLM 且轮到 AI:
   │         └─► 启动 EngineWorker(is_maid_llm=True) ──► LLMAgent.get_move() (结构化JSON) ──► apply_move()
   ├─► 判定自动教学触发:
   │    └─► 若 TeachingTriggers 开启 ──► MainWindow._dispatch_llm_request()
   │         └─► 启动 LLMWorker ──► LLMAgent.reply() (流式) ──► ChatPanel 逐字渲染
   └─► 判定终局:
        └─► 若 Game Over ──► evaluate_game_moves_quality() (全盘评估) 
             ──► 后台守护线程异步生成 LLM 复盘总结 
             ──► HistoryStore.save_game(pgn, result, summary) 
             ──► LongTermMemory.record_game_result()
             ──► emit game_over
```

---

## 五、未来功能扩展标准契约

1. **新增 Agent 角色**：继承 `src.agents.base.ChessAgent`，实现 `reply(self, request: AgentRequest, on_chunk=None, is_cancelled=None) -> str`。
2. **新增自定义工具**：在 `AgentTools` 中扩充方法并在 `LLMAgent._get_tools_definitions()` 中注册对应 JSON Schema。
