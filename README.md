# ChessMaidBot - 国际象棋 AI 女仆教学对弈系统

> **Vibe Coding 竞赛项目**：融合国际象棋规则引擎、Stockfish 深度分析与个性化 LLM 女仆陪练的智能教学对弈桌面应用。

---

## 目录
- [一、项目愿景与核心特性](#一项目愿景与核心特性)
- [二、软件架构概览（六大模块）](#二软件架构概览六大模块)
- [三、环境配置与快速启动](#三环境配置与快速启动)
- [四、项目目录结构](#四项目目录结构)
- [五、核心模块开发与接入指引](#五核心模块开发与接入指引)
- [六、测试与质量保证](#六测试与质量保证)
- [七、团队与 AI 协作规范](#七团队与-ai-协作规范)

---

## 一、项目愿景与核心特性

ChessMaidBot 旨在打破传统国际象棋软件冷冰冰的对弈体验，通过**拟人化 AI 棋艺女仆**为棋手提供全方位的陪伴、鼓励与战术复盘：
1. **交互式棋盘**：基于 PySide6 自研纯矢量高清直绘棋盘，支持流畅拖拽、点击选格、高亮警示与 Lichess 风格王车易位。
2. **多模式对弈**：支持本地双人对弈、人机对弈（Stockfish 引擎）、AI 女仆陪练对弈（LLM 驱动）。
3. **多级教学触发器**：具备教学总开关及“当下局面评估、建议着法、历史走法预警、终局复盘总结”四大细分触发器。
4. **历史棋局自动归档**：终局自动生成标准 PGN 棋谱并持久化归档至历史棋局库。
5. **Stockfish 引擎无缝联动**：封装 UCI 通信协议，支持 0~20 级细粒度强度调节与 MultiPV 多着法打分分析。

---

## 二、软件架构概览（六大模块）

本系统严格采用 **MVC 架构分层** 与 **单一数据源（Single Source of Truth）** 设计：

```
┌─────────────────────────────────────────────────────────────┐
│ 模块 1: GUI 交互界面 (src/gui/)                              │
│ 交互式棋盘 / 双栏记谱表 / LLM 对话窗口 / 顶部控制栏 / 升变对话框     │
└──────────────────────────────┬──────────────────────────────┘
                               │ 意图信号 (move_ready / undo / new_game)
┌──────────────────────────────▼──────────────────────────────┐
│ 模块 2: Controller 调度中枢层 (src/controller/)               │
│ GameController (唯一写路径) / GameModeManager / TeachingTriggers │
└──────────────┬──────────────┬──────────────┬────────────────┘
               │              │              │
┌──────────────▼───┐ ┌────────▼──────────┐ ┌─▼────────────────┐
│ 模块 3: 规则核心  │ │ 模块 4: 引擎调度   │ │ 模块 6: 数据库存储 │
│ src/core/        │ │ src/engine/        │ │ src/database/      │
│ 局面状态管理      │ │ Stockfish 客户端   │ │ 历史棋局库 (PGN)   │
│ 双栏记谱 & 快照   │ │ UCI 协议与分析     │ │ 开局/战术库(规划中)│
└──────────────────┘ └────────┬──────────┘ └──────────────────┘
                              │
                     ┌────────▼──────────┐
                     │ 模块 5: Agent 接口 │
                     │ src/agents/       │
                     │ 标准格式请求包    │
                     │ LLM 女仆陪练/解说 │
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
│   ├── config.py               # 全局配置、主题、Prompt 与路径定义
│   ├── core/                   # [模块3] 规则核心与记谱 (BoardState, MoveHistoryManager)
│   ├── controller/             # [模块2] 调度层 (GameController, GameModeManager, TeachingTriggers)
│   ├── engine/                 # [模块4] Stockfish UCI 通信客户端 (StockfishClient)
│   ├── agents/                 # [模块5] Agent 抽象与标准请求格式 (ChessAgent, AgentRequest)
│   ├── database/               # [模块6] 历史棋局库持久化存储 (HistoryStore)
│   └── gui/                    # [模块1] PySide6 视图组件 (棋盘、聊天框、记谱表等)
└── tests/                      # 单元测试与集成测试 (46+ 测试用例)
```

---

## 五、核心模块开发与接入指引

### 1. 接入真实 LLM（模块5）
继承 `src.agents.base.ChessAgent`，实现 `reply(self, request: AgentRequest) -> str`：
```python
from src.agents.base import ChessAgent, AgentRequest

class MyCustomLLMAgent(ChessAgent):
    def reply(self, request: AgentRequest) -> str:
        # request 中包含：
        # - request.user_message: 用户提问
        # - request.persona_prompt: 女仆人设 Prompt
        # - request.snapshot: 包含 FEN, PGN, 行棋方, 是否将军, 最近着法
        prompt = f"{request.persona_prompt}\n当前局面 FEN: {request.snapshot.fen}\n问题: {request.user_message}"
        # 调用大模型 API 并返回 Markdown 文本
        return "女仆的分析回复内容..."
```

### 2. 调用 Stockfish 引擎分析（模块4）
```python
from src.engine import StockfishClient

with StockfishClient() as engine:
    engine.set_skill_level(15)  # 0(最弱) ~ 20(最强)
    best_move = engine.best_move(fen, movetime_ms=1000)
    top_moves = engine.analyse(fen, depth=12, multipv=3)  # 获取前 3 推荐走法
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
