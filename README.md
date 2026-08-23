# ChessMaidBot - 国际象棋 AI 女仆教学对弈系统

> **Vibe Coding 竞赛项目**：融合国际象棋规则引擎、Stockfish 深度分析与个性化 LLM 女仆陪练的智能教学对弈桌面应用。

---

## 目录
- [一、项目愿景与核心特性](#一项目愿景与核心特性)
- [二、设计功能完成度清单（已完成 vs 尚未完成）](#二设计功能完成度清单已完成-vs-尚未完成)
- [三、软件架构概览（六大模块）](#三软件架构概览六大模块)
- [四、环境配置与快速启动](#四环境配置与快速启动)
- [五、项目目录结构](#五项目目录结构)
- [六、核心模块开发与接入指引](#六核心模块开发与接入指引)
- [七、测试与质量保证](#七测试与质量保证)
- [八、团队与 AI 协作规范](#八团队与-ai-协作规范)

---

## 一、项目愿景与核心特性

ChessMaidBot 旨在打破传统国际象棋软件冷冰冰的对弈体验，通过**拟人化 AI 棋艺女仆**为棋手提供全方位的陪伴、鼓励与战术复盘：
1. **现代三栏版面布局**：左侧对局记谱表、中央核心交互式棋盘、右侧 LLM 女仆交互对话窗口，提供沉浸式对弈视界。
2. **人机对弈与目标 Elo 评级分控制**：支持通过 Stockfish 官方 UCI 参数控制目标 Elo（1320 ~ 3190），配合异步后台计算线程，对局流畅不卡顿。
3. **完整对局流程支持**：支持认输（Resign）、协议提和/规则和棋申诉（Offer/Claim Draw）、新对局与悔棋。
4. **复合历史棋局归档**：以“标准 PGN 棋谱 + LLM 终局复盘总结”复合格式持久化至历史棋局库，彻底解决 LLM 纯文本读谱缺陷。
5. **多级教学触发器**：具备教学总开关及“当下局面评估、建议着法、历史走法预警、终局复盘总结”四大细分触发器。

---

## 二、设计功能完成度清单（已完成 vs 尚未完成）

| 模块 | 功能设计点 | 状态 | 说明 |
|---|---|---|---|
| **1. GUI 交互界面** | 交互式棋盘（矢量绘图、拖拽、点击、Lichess 风格王车易位、升变弹窗） | ✅ 已完成 | 高清抗锯齿，完全响应调度层信号 |
| | LLM 对话窗口（Markdown 气泡流、快捷提问条、输入框） | ✅ 已完成 | 支持对话流与 5 级教学触发器动态勾选联动 |
| | 现代三栏布局（左: 记谱表, 中: 棋盘, 右: 对话窗口） | ✅ 已完成 | 居中沉浸式对弈视界 |
| | 认输（🏳️ 认输）与 求和（🤝 求和）按钮交互 | ✅ 已完成 | 支持二次确认与协议/规则判定 |
| | 推荐走法列表（非核心） | ⏳ 尚未完成（非核心） | 涉及 LLM 建议与 Stockfish 引擎推荐冲突切换，预留扩展插槽 |
| **2. Controller 调度层** | 对弈模式管理器（本地双人、人机对弈） | ✅ 已完成 | 模式状态机与对局元数据无缝衔接 |
| | 人机对弈后台异步走子（`EngineWorker` 线程） | ✅ 已完成 | 计算时不卡顿 UI，算完自动投递走法并锁定/解锁棋盘 |
| | 网络双人对弈（非核心） | ⏳ 尚未完成（非核心） | 预留接口，网络通信协议待后续接入 |
| | 教学触发器总开关与 4 级细分开关 | ✅ 已完成 | 包含当前评估、建议着法、历史走法预警、棋局结束总结 |
| **3. 规则核心** | 国际象棋规则判定（python-chess 封装、合法性、吃过路兵、被吃子堆栈） | ✅ 已完成 | 具备单一数据源校验与防越界回滚机制 |
| | PGN / FEN 编解码与无损导入导出 | ✅ 已完成 | 支持黑先开局占位记谱与撤销 |
| | 树形变例生成（平行棋局分支，非核心） | ⏳ 尚未完成（非核心） | 每步记录均已持久化 `fen_after`，预留分支调用接口 |
| **4. Stockfish 引擎** | UCI 命令行通信封装（`StockfishClient`） | ✅ 已完成 | 支持 stdin/stdout 流式解析、容错降级 |
| | 目标 Elo 控制（`UCI_LimitStrength` + `UCI_Elo`） | ✅ 已完成 | 支持 1320 ~ 3190 连续 Elo 调节与 Skill Level (0~20) 调节 |
| | 多 PV 着法分析与评分（`analyse` / `get_state`） | ✅ 已完成 | 提供引擎状态统一读取能力 |
| **5. Agent 接口与方法库** | 自定义 LLM 人设 Prompt 注入与打包 | ✅ 已完成 | 支持动态设置 Prompt 并随请求下发 |
| | 标准化上下文请求包（`AgentRequest`） | ✅ 已完成 | 封装 FEN、PGN、行动方、将军状态与对局快照 |
| | LLM 外部方法库（`AgentTools` 4 大方法） | ✅ 已完成 | 允许自主决定是否读取及读取数据库/引擎状态哪部分 |
| | 真实在线 LLM API 接入（如 DeepSeek/OpenAI） | ⏳ 尚未完成（测试期使用 EchoAgent 占位） | 提供标准基类与注入模板，可直接接入 API key |
| **6. 数据库** | 历史棋局库持久化（PGN + LLM 总结复合格式） | ✅ 已完成 | 写入 `data/games/`，支持双向拆解与查询检索 |
| | 开局库、EPD 编码战术库、残局库接入 | ⏳ 尚未完成（已预留统一查询接口） | `query_database` 接口已抽象完备，等待数据文件填充 |

---

## 三、软件架构概览（六大模块）

本系统严格采用 **MVC 架构分层** 与 **单一数据源（Single Source of Truth）** 设计：

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 模块 1: GUI 交互界面 (src/gui/)                                          │
│ [左] 走法历史记谱表  │  [中] 交互式棋盘+状态栏  │  [右] LLM 对话窗口+教学触发器 │
│ 顶部控制栏: 模式选择 / Stockfish Elo 微调 / 认输 / 求和 / 导出 PGN & FEN   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ 意图信号 (move_ready / resign / draw)
┌────────────────────────────────────▼────────────────────────────────────┐
│ 模块 2: Controller 调度中枢层 (src/controller/)                           │
│ GameController (唯一写路径) / GameModeManager / EngineWorker 异步线程     │
└──────────────┬─────────────────────┬─────────────────────┬──────────────┘
               │                     │                     │
┌──────────────▼───┐        ┌────────▼──────────┐ ┌────────▼──────────────┐
│ 模块 3: 规则核心  │        │ 模块 4: 引擎调度   │ │ 模块 6: 数据库存储   │
│ src/core/        │        │ src/engine/        │ │ src/database/        │
│ 局面状态管理      │        │ Stockfish 客户端   │ │ 历史棋局库 (PGN+总结)│
│ 双栏记谱 & 快照   │        │ 目标 Elo / UCI 通信│ │ 开局/战术/残局库接口 │
└──────────────────┘        └────────┬──────────┘ └───────────────────────┘
                                     │ (提供引擎分析)
                            ┌────────▼──────────┐
                            │ 模块 5: Agent 接口 │
                            │ src/agents/       │
                            │ 标准格式请求包    │
                            │ AgentTools 工具集 │
                            └───────────────────┘
```

> **详细架构说明请查阅**：[`ARCHITECTURE.md`](./ARCHITECTURE.md)

---

## 三、环境配置与快速启动

### 1. 安装系统依赖与 Python 环境 (推荐 Python 3.10+)

```bash
# 1. 克隆代码仓库
git clone git@github.com:ZhRuYun/ChessMaidBot.git
cd ChessMaidBot

# 2. 安装 Python 依赖
pip install -r requirements.txt
```

### 2. 配置 Stockfish 引擎（可选但推荐）

- 引擎可执行文件默认存放于 `engines/stockfish`。
- Linux (x86_64) 可直接运行官方 release 二进制并赋予执行权限：
  ```bash
  chmod +x engines/stockfish
  ```
- Windows 用户请下载 `stockfish-windows-x86-64-avx2.exe` 并重命名为 `engines/stockfish.exe`。

### 3. 运行程序

```bash
python3 main.py
```

---

## 四、项目目录结构

```
ChessMaidBot/
├── main.py                     # 程序启动入口
├── requirements.txt            # Python 依赖清单
├── README.md                   # 项目总说明文档
├── ARCHITECTURE.md             # 架构全景与接口详细设计文档
├── AGENTS.md                   # AI 协作与二次开发规范
├── assets/                     # 静态资源（矢量棋子 SVG 图标等）
├── engines/                    # 引擎存放目录（放入 stockfish 二进制）
├── data/                       # 运行期产生的数据（历史棋局自动存入 data/games/）
├── src/                        # 核心源代码
│   ├── config.py               # 全局配置、主题、Prompt、Elo 范围与路径定义
│   ├── core/                   # [模块3] 规则核心与记谱 (BoardState, MoveHistoryManager)
│   ├── controller/             # [模块2] 调度层 (GameController, GameModeManager, EngineWorker)
│   ├── engine/                 # [模块4] Stockfish UCI 通信客户端 (StockfishClient)
│   ├── agents/                 # [模块5] Agent 抽象与标准请求格式 (ChessAgent, AgentRequest, AgentTools)
│   ├── database/               # [模块6] 历史棋局库持久化存储 (HistoryStore, PGN+总结解析)
│   └── gui/                    # [模块1] PySide6 视图组件 (中央棋盘、左侧记谱表、右侧聊天框等)
└── tests/                      # 单元测试与集成测试 (50+ 测试用例，100% 通过)
```

---

## 五、核心模块开发与接入指引

### 1. 接入真实 LLM（模块5）
继承 `src.agents.base.ChessAgent`，实现 `reply(self, request: AgentRequest) -> str`：
```python
from src.agents.base import ChessAgent, AgentRequest

class MyCustomLLMAgent(ChessAgent):
    def reply(self, request: AgentRequest) -> str:
        # 1. 检查 request.tools 是否可用，按需读取数据库或引擎评估
        if request.tools and request.tools.read_engine_state:
            eval_info = request.tools.read_engine_state(state_type="analyse", params={"depth": 10})
        # 2. 结合 request.snapshot、人设和用户提问调用 LLM
        return "女仆的分析回复内容..."
```

### 2. 控制 Stockfish 引擎 Elo 与多 PV 分析（模块4）
```python
from src.engine import StockfishClient

with StockfishClient() as engine:
    engine.set_elo(1800)  # 精准目标 Elo 等级分 (1320 ~ 3190)
    best_move = engine.best_move(fen, movetime_ms=600)
    top_moves = engine.analyse(fen, depth=12, multipv=3)
```

---

## 六、测试与质量保证

项目采用标准 `unittest` 构建了全面的测试矩阵（覆盖规则、记谱、控制器、数据库、引擎客户端及离屏 GUI 链路）：

```bash
# 运行全部测试（无图形界面环境下）
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests
```

---

## 七、团队与 AI 协作规范

1. **人类开发者**：在添加新功能前，请通读 [`ARCHITECTURE.md`](./ARCHITECTURE.md)，保持分层清晰。
2. **AI 模型（LLM/Coding Agent）**：
   - **所有协助修改代码的 AI 模型必须强制遵循 [`AGENTS.md`](./AGENTS.md) 的规则**。
   - 严禁绕过 `GameController` 直接在 GUI 中修改棋局规则状态。
   - 任何新增接口或模块结构变更，**必须同步更新相关文档**。

