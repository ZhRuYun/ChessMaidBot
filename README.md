# ChessMaidBot - 国际象棋 AI 女仆教学对弈系统

> **全功能智能桌面应用**：融合国际象棋规则引擎、Stockfish 深度分析评估、长短期双层记忆系统与个性化多角色 LLM 女仆陪练的智能教学对弈桌面系统。
> **注意**：项目处于beta测试阶段，LLM功能处于剧烈修改期间，建议使用**Commit 32acbbb**来稳定体验

---

## 目录
- [一、项目愿景与核心特性](#一项目愿景与核心特性)
- [二、系统功能全景完成度](#二系统功能全景完成度)
- [三、架构全景与六大模块](#三架构全景与六大模块)
- [四、环境配置与快速启动](#四环境配置与快速启动)
- [五、项目工程目录结构](#五项目工程目录结构)
- [六、AI 女仆与 LLM 核心机制](#六ai-女仆与-llm-核心机制)
- [七、对弈模式与 Coach 复盘系统](#七对弈模式与-coach-复盘系统)
- [八、测试与质量保证](#八测试与质量保证)
- [九、开发协作与规范文档索引](#九开发协作与规范文档索引)

---

## 一、项目愿景与核心特性

ChessMaidBot 旨在打破传统国际象棋软件冷冰冰的对弈体验，通过**拟人化 AI 棋艺女仆**为棋手提供全方位的陪伴、实时战术提示、长短期记忆成长与深度复盘：

1. **现代三栏交互版面**：
   - **左侧**：走法双栏记谱表（支持 Lichess 风格历史步数自由跳转与预览）。
   - **中央**：自研矢量高清抗锯齿棋盘，支持拖拽/点击、王车易位、升变选择与将军预警。
   - **右侧**：LLM 女仆实时对话窗口，支持 Markdown 格式化、SSE 流式打字机效果与实时 Loading Spinner。
2. **多模式对弈与精准 Elo 控制**：
   - 支持**本地双人对弈**、**人机 Stockfish 对弈**（500 ~ 3190 Elo 精准控制）、**女仆 LLM 陪练**（结构化走子决策与劣势悔棋请求）、**局域网/网络双人对战**（内置 WebSocket 实时全双工服务与客户端）。
3. **长短期双层记忆系统 (Memory System)**：
   - **短期工作记忆 (ShortTermMemory)**：维护当前对局滑动窗口对话历史，彻底消除多轮对话断链与失忆问题。
   - **长期画像记忆 (LongTermMemory)**：跨对局持久化记录玩家总胜率、偏好开局、常见失误类型与棋风标签，使女仆具备陪伴成长感。
4. **结构化输出与防注入防御**：
   - 女仆对弈采用 OpenAI 兼容 `json_object` 结构化输出与 Schema 严格校验，彻底杜绝正则提取异常与思考模型（Reasoning Models）解析失效。
   - Prompt 引入 `<!-- BEGIN_TRUSTED_CHESS_DATA -->` 与 `<!-- SYSTEM_GUARD -->` 防注入护栏。
5. **Coach Mode 全盘复盘与复合历史归档**：
   - 自动评估全盘着法质量（Best, Excellent, Good, Inaccuracy, Mistake, Blunder），以“标准 PGN 棋谱 + LLM 战术复盘总结”复合结构异步持久化至历史棋局库。

---

## 二、系统功能全景完成度

| 模块 | 功能设计点 | 状态 | 核心实现与细节说明 |
|---|---|---|---|
| **1. GUI 交互界面** | 交互式棋盘 | ✅ 已完成 | 矢量 SVG 直绘，抗锯齿，居中防偏移，支持点击与拖拽，将军警示红高亮 |
| | 步数导航与预览 | ✅ 已完成 | 首步、上一步、下一步、最后一步导航，点击历史步数即时呈现预览棋盘 |
| | LLM 对话交互 | ✅ 已完成 | 现代深色/浅色气泡流，Markdown 排版，SSE 流式逐字渲染，Loading 动画 |
| | 主题系统 | ✅ 已完成 | 跟随系统、浅色、深色三档平滑切换，记谱表与对话框全局色彩联动适配 |
| | 认输/求和/导入导出 | ✅ 已完成 | 协议和棋与规则申诉（50步/3度重复），一键智能导入导出 PGN 与 FEN |
| | 综合 AI 配置面板 | ✅ 已完成 | 统一配置 API Base、Key、模型拉取、思考档位、流式开关、搜索接口与人设模板 |
| **2. Controller 调度层** | 状态唯一写入口 | ✅ 已完成 | 单一数据源设计，所有走法、悔棋、重开经信号广播，杜绝状态竞态 |
| | 4 种对弈模式 | ✅ 已完成 | 本地双人、人机对弈、女仆 LLM 陪练、网络双人联机（内置服务端/客户端） |
| | 引擎多线程异步调度 | ✅ 已完成 | `EngineWorker` QThread 后台计算，代际号（Generation）丢弃机制防悬挂 |
| | 教学触发器 | ✅ 已完成 | 教学总开关 + 局面评估、建议着法、历史走法失误预警、终局复盘 4 级子开关 |
| **3. 规则核心** | 国际象棋规则引擎 | ✅ 已完成 | 基于 `python-chess` 封装，合法性校验、吃过路兵、被吃子栈与防越界回滚 |
| | 记谱与状态重演 | ✅ 已完成 | `MoveHistoryManager` 双栏记谱，黑先开局占位记谱，PGN/FEN 互转 |
| **4. Stockfish 引擎** | UCI 协议通信 | ✅ 已完成 | `StockfishClient` 进程管理，标准 stdin/stdout 流式解析与容错降级 |
| | 目标 Elo 控制 | ✅ 已完成 | 官方 `UCI_LimitStrength` + `UCI_Elo`，支持 500 ~ 3190 连续 Elo 精度调节 |
| | 多 PV 分析与共享池 | ✅ 已完成 | `SharedEngine` 进程级互斥复用池，多 PV 分析与估分，避免重复拉起进程 |
| **5. Agent 与记忆层** | 结构化输出与决策 | ✅ 已完成 | `json_object` 规范输出 + 非法着法自纠错重试 + Stockfish 兜底来源披露（已移除随机走法） |
| | 双层记忆机制 | ✅ 已完成 | `ShortTermMemory` 意图标签瘦身上下文 + `LongTermMemory` 画像（终局自动回填开局/失误） |
| | 语义缓存与模板注册表 | ✅ 已完成 | `SemanticCache` 同局面复用回复；`prompt_registry` 模板版本化管理 |
| | HTTP 韧性与可观测 | ✅ 已完成 | 429/5xx 分类退避、总超时、取消贯通、Token 用量统计与统一日志 |
| | 自主 Tool Calling | ✅ 已完成 | 提供开局库查询、历史检索、引擎深度分析、联网搜索与悔棋申请 5 大工具 |
| | 多角色协同 | ✅ 已完成 | `MultiRoleCoordinator` 两段式流水线：教练 JSON 结构化分析 → 女仆人格化改写 |
| **6. 数据库与归档** | 复合历史棋局库 | ✅ 已完成 | `data/games/` 异步保存 `PGN + LLM 总结`，自动过滤 0 步/无效对局；支持关键词检索（RAG-lite） |
| | 开局库与题库 | ✅ 已完成 | `data/books/` 集成 Lichess 开源开局库与 Polyglot，支持 ECO 与权重推荐 |

---

## 三、架构全景与六大模块

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 模块 1: GUI 交互界面 (src/gui/)                                          │
│ [左] 走法记谱表  │  [中] 交互式棋盘 + 状态指示  │  [右] LLM 对话 + 教学配置     │
│ 顶部控制栏: 模式切换 / 目标 Elo 调节 / 认输 / 求和 / 导入导出 PGN+FEN / 主题     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ 仅发用户意图 (move_ready / resign / draw)
┌────────────────────────────────────▼────────────────────────────────────┐
│ 模块 2: Controller 调度中枢层 (src/controller/)                           │
│ GameController (唯一写入口) / GameModeManager / EngineWorker 异步工作线程 │
└──────────────┬─────────────────────┬─────────────────────┬──────────────┘
               │                     │                     │
┌──────────────▼───┐        ┌────────▼──────────┐ ┌────────▼──────────────┐
│ 模块 3: 规则核心  │        │ 模块 4: 引擎调度   │ │ 模块 6: 数据库存储   │
│ src/core/        │        │ src/engine/        │ │ src/database/        │
│ ├── BoardState   │        │ ├── StockfishClient│ │ ├── HistoryStore     │
│ └── MoveHistory- │        │ └── SharedEngine   │ │ ├── OpeningBook      │
│     Manager      │        │     (共享引擎池)   │ │ └── UnifiedDatabase  │
└──────────────────┘        └────────┬──────────┘ └───────────────────────┘
                                     │ (提供引擎分析)
                            ┌────────▼──────────┐
                            │ 模块 5: Agent 接口 │
                            │ src/agents/       │
                            │ ├── LLMAgent      │
                            │ ├── Memory (双层) │
                            │ ├── Multi-Role    │
                            │ └── PromptBuilder │
                            └───────────────────┘
```

---

## 四、环境配置与快速启动

### 1. 环境准备 (推荐 Python 3.10 ~ 3.12)

```bash
# 1. 克隆代码仓库
git clone git@github.com:ZhRuYun/ChessMaidBot.git
cd ChessMaidBot

# 2. 安装 Python 依赖
pip install -r requirements.txt
```

### 2. 配置 Stockfish 引擎与开局库资产

项目提供了一键自动拉取与编译配置脚本：
```bash
python3 scripts/download_assets.py
```
- Linux (x86_64)：自动下载官方可执行文件至 `engines/stockfish` 并赋予执行权限。
- Windows：将下载的 `stockfish-windows-x86-64-avx2.exe` 放入 `engines/stockfish.exe`。
- 开局库：自动从 Lichess 仓库下载并构建 `data/books/openings.json`。

### 3. 运行应用程序

```bash
python3 main.py
```

---

## 五、项目工程目录结构

```
ChessMaidBot/
├── main.py                     # 程序启动主入口
├── requirements.txt            # 项目依赖 (python-chess, PySide6, markdown)
├── README.md                   # 项目总说明文档
├── docs/                       # 核心设计与规范文档
│   ├── ARCHITECTURE.md         # 架构全景与详细接口设计文档
│   ├── AGENTS.md               # Agent 接口、Prompt 标准与工具调用规范
│   └── CUSTOM_CONFIG_GUIDE.md  # 详细自定义配置与二次开发指南
├── assets/                     # 静态资源 (12 枚矢量棋子 SVG 图标等)
├── engines/                    # Stockfish 引擎二进制存放目录
├── data/                       # 统一运行时持久化数据目录 (已被 .gitignore 保护)
│   ├── games/                  # 历史棋局库 (*.pgn + LLM 总结)
│   ├── books/                  # 开局库 (openings.json, titans.bin)
│   ├── settings.json           # 持久化设置 (API、人设、搜索配置)
│   └── player_profile.json     # 长期记忆：玩家偏好与对弈画像
├── src/                        # 核心源代码
│   ├── config.py               # 全局配置、主题、Prompt 与常量
│   ├── core/                   # [模块3] 规则核心 (BoardState, MoveHistoryManager)
│   ├── controller/             # [模块2] 调度层 (GameController, GameModeManager, EngineWorker)
│   ├── engine/                 # [模块4] Stockfish UCI 客户端与 SharedEngine 共享池
│   ├── agents/                 # [模块5] LLM 客户端、双层记忆、多角色与 PromptBuilder
│   ├── database/               # [模块6] 历史棋局库持久化、开局库与 UnifiedDB
│   └── gui/                    # [模块1] PySide6 视图组件 (棋盘、记谱表、聊天框、弹窗)
├── scripts/                    # 资源一键下载安装脚本
└── tests/                      # 单元测试集 (覆盖 6 大模块)
```

---

## 六、AI 女仆与 LLM 核心机制

1. **结构化输出与走法决策 (`LLMAgent.get_move`)**：
   - 彻底告别脆弱的正则表达式。在女仆对弈模式下，通过向 LLM 注入合法 UCI 着法白名单并强制要求返回严格的 JSON Schema / Object（`{"thought": "...", "best_move_uci": "e2e4"}`），支持非法着法带反馈自纠错重试，解析异常时自动通过 Stockfish 引擎或开局库平滑降级。
2. **多轮对话上下文管理 (`ShortTermMemory`)**：
   - 调度层自动追踪对话事件流，向 LLM 动态注入最近 10 轮历史对话，支持基于上下文的连续追问与棋理探讨。
3. **长期画像积累与 LLM 战术蒸馏 (`LongTermMemory`)**：
   - 跨对局自动归档胜负数据、偏好开局与高频失误，自动为玩家打上棋风标签（如“沉稳战术型”），并在终局复盘中自动蒸馏关键弱点与教练重点建议，在后续对弈中提供高度个性化指导。
4. **自主 Tool Calling 与去冗余调用**：
   - 移除 System Prompt 中的硬编码前置数据抓取，支持模型在推理过程中按需调用 `engine_analyze`、`query_opening_book`、`query_game_history`、`search_chess_knowledge` 与 `request_undo`（带单局去重限流）。
5. **弹性流式传输与自愈机制 (`ResilientStreamParser`)**：
   - 内置 UTF-8 增量解码器，彻底杜绝字节流截断导致的中文乱码（U+FFFD）；支持 SSE 逐字流式打字机渲染与请求在途主动取消；具备 Markdown 未闭合代码块自动修复能力。
6. **落子自动教学单向门控**：
   - 仅针对人类玩家自身走棋触发自动教学，避免 AI 自身落子重复请求导致 Token 翻倍与请求相互中断，大幅降低使用成本并提升交互稳定性。
7. **异步非阻塞运维与安全存储**：
   - 连接测试与远端模型拉取通过 `FetchModelsWorker` 异步执行，杜绝 UI 冻结；配置凭据通过 600 权限用户私有化保护，用量统计与引擎互斥全链路线程安全。

---

## 七、对弈模式与 Coach 复盘系统

### 1. 对弈模式
- **本地双人对弈 (Local PvP)**：支持本地双人轮流落子，自由推演棋局。
- **人机 Stockfish 对弈 (VS Engine)**：支持 500 到 3190 Elo 连续精度调节，配备 5 档经典预设（新手/业余/职业/大师/特级大师），支持执白/执黑自由选边。
- **女仆 LLM 陪练 (VS Maid LLM)**：直接与大语言模型对弈，模型在面临绝境（评估分落后过大）时会自动向玩家发起拟人化悔棋请求。
- **网络双人对战 (Online PvP)**：内置嵌入式轻量通信服务与客户端，一键开房/连房对战。

### 2. Coach Mode 全盘复盘
终局时，系统后台自动调用引擎对全盘走法逐步计算评估落差（$\Delta \text{cp}$），为每一步打上质量标签：
- `Best` (最优手) / `Excellent` (绝妙手) / `Good` (好棋)
- `Inaccuracy` (缓手) / `Mistake` (疑问手) / `Blunder` (严重败着)
系统将全盘失误转折点整理为教练报告，并由 LLM 生成生动透彻的复盘总结，写入复合 PGN 文件。

---

## 八、测试与质量保证

项目采用标准 `pytest` 与 `unittest` 构建了全面的测试矩阵：

```bash
# 运行全部单元测试
PYTHONPATH=. pytest

# 离屏/无图形界面环境下运行
QT_QPA_PLATFORM=offscreen PYTHONPATH=. pytest
```

---

## 九、开发协作与规范文档索引

- **架构设计全景与时序图**：详见 [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- **Agent 开发与工具调用规范**：详见 [`docs/AGENTS.md`](./docs/AGENTS.md)
- **自定义配置与二次开发教程**：详见 [`docs/CUSTOM_CONFIG_GUIDE.md`](./docs/CUSTOM_CONFIG_GUIDE.md)
