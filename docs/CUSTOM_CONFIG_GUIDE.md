# ChessMaidBot 自定义配置与二次开发全景指南

本文档全面介绍 ChessMaidBot 中所有支持自定义配置的功能模块、持久化格式、参数细节与二次开发扩展方法。

---

## 目录
1. [一、数据库目录与开局库自定义](#一一数据库目录与开局库自定义)
2. [二、Stockfish 引擎配置与 Elo 精准控制](#二二stockfish-引擎配置与-elo-精准控制)
3. [三、双层记忆系统配置与玩家档案](#三三双层记忆系统配置与玩家档案)
4. [四、女仆人设与 Prompt 自定义](#四四女仆人设与-prompt-自定义)
5. [五、棋盘与界面主题配色](#五五棋盘与界面主题配色)
6. [六、教学触发器配置](#六六教学触发器配置)
7. [七、AI 综合设置与在线 LLM 接入](#七七ai-综合设置与在线-llm-接入)
8. [八、网络双人联机服务配置](#八八网络双人联机服务配置)

---

## 一、数据库目录与开局库自定义

所有运行时数据与题库统一收拢在项目根目录的 `data/` 目录下（已被 `.gitignore` 保护）：

```
data/
├── games/               # 自动存放持久化的历史棋局 (.pgn + LLM总结)
├── books/               # 开局库目录 (openings.json / titans.bin)
├── settings.json        # 用户持久化配置 (API Base, Key, 模型, 人设等)
└── player_profile.json  # 长期记忆：玩家画像与胜率、偏好开局档案
```

### 1.1 开局库 (Lichess 开源开局库 / Polyglot)
- **JSON 格式**：`data/books/openings.json`（基于 Lichess 开源库，包含 ECO 编码、开局名称及候选走法权重）。
- **Polyglot 格式**：支持标准 `.bin` 格式开局库（默认路径 `data/books/titans.bin`）。
- **一键更新**：运行 `python3 scripts/download_assets.py` 即可自动拉取最新开局库。

### 1.2 玩家历史棋局归档
- **过滤标准**：只有玩家正常完赛（将死、被将死、认输、协议求和等）的对局才会存入 `data/games/`。0 步棋局或未开局棋局自动过滤。
- **复合格式**：采用 `标准 PGN 记谱 + % --- LLM GAME SUMMARY ---` 复合结构，便于解析器与 LLM 双向无损读取。

---

## 二、Stockfish 引擎配置与 Elo 精准控制

配置文件位于 `src/config.py`。

### 2.1 引擎可执行文件路径
```python
# Windows 自动识别 stockfish.exe，Linux/macOS 识别 stockfish
ENGINE_PATH = ENGINE_DIR / ("stockfish.exe" if sys.platform == "win32" else "stockfish")
```

### 2.2 Elo 评级分与技能等级映射
Stockfish 官方限制强度范围为 1320 ~ 3190。系统内置了自适应降级算法，支持 500 ~ 3190 的全区间连续调节：
```python
STOCKFISH_DEFAULT_SKILL = 10     # 默认 Skill Level (0 ~ 20)
STOCKFISH_DEFAULT_ELO = 1500     # 默认目标 Elo 等级分
STOCKFISH_MIN_ELO = 500          # 支持的最低 Elo (低于 1320 时自动映射 Skill Level 降级)
STOCKFISH_MAX_ELO = 3190         # 支持的最高 Elo

# 预设 5 大经典档位
STOCKFISH_ELO_PRESETS = [
    ("新手", 500),
    ("业余", 1000),
    ("职业", 1500),
    ("大师", 2000),
    ("特级大师", 2500),
    ("自定义", -1),
]
```

---

## 三、双层记忆系统配置与玩家档案

位于 `src/agents/memory.py`：

### 3.1 短期工作记忆 (`ShortTermMemory`)
- 默认保留最近 12 轮对话上下文窗口，可根据需要在 `MainWindow` 中初始化时调整 `max_turns`。

### 3.2 长期画像记忆 (`LongTermMemory`)
- 自动维护 `data/player_profile.json`，结构如下：
```json
{
  "total_games": 18,
  "wins": 10,
  "losses": 6,
  "draws": 2,
  "favorite_openings": {
    "Sicilian Defense": 8,
    "Queen's Gambit": 5
  },
  "frequent_blunders": {
    "Nf6": 2
  },
  "playstyle_tag": "沉稳战术型"
}
```

---

## 四、女仆人设与 Prompt 自定义

在 `src/config.py` 中定义全局默认人设 `DEFAULT_MAID_PERSONA`：

```python
DEFAULT_MAID_PERSONA = (
    "你是一位精通国际象棋且温柔细致的AI棋艺女仆助理【ChessMaid】。"
    "你的核心职责是陪伴主人对弈并提供富有洞察力的战术指导与大局观教学。"
    "在解答与指导时：\n"
    "1. 语言亲切得体、条理清晰，优先剖析空间、子力协调、王安全与关键格控制等核心棋理。\n"
    "2. 指出走法意图与战术威胁，给出清晰可行的后续计划。\n"
    "3. 根据主人的提问或局势按需给出最推荐的合法着法与深度分析。\n"
    "4. 严禁废话与套话，严禁输出任何emoji表情符号。"
)
```

用户在 GUI 界面中修改人设后，会自动持久化至 `data/settings.json` 的 `persona` 字段中。

---

## 五、棋盘与界面主题配色

在 `src/config.py` 的 `BOARD_THEME` 字典中自定义配色：

```python
BOARD_THEME = {
    "light_square": "#EADECA",          # 浅色柔和米白木纹
    "dark_square": "#B38B6D",           # 沉稳深色胡桃木纹
    "highlight_selected": "#7FA650",    # 选中格清爽浅绿高亮
    "highlight_last_move": "#C5D14E",   # 上步走法明快黄绿高亮
    "highlight_check": "#EF4444",       # 将军警示红
    "move_indicator": "#4B6B38",        # 合法走法圆点
    "capture_indicator": "#4B6B38",     # 合法吃子圆环
}

# 棋盘网格尺寸 (默认 64px，总尺寸 512×512)
DEFAULT_SQUARE_SIZE = 64
BOARD_SIZE = DEFAULT_SQUARE_SIZE * 8
```

---

## 六、教学触发器配置

通过 `TeachingTriggers` 控制对弈教学的主被动行为：

```python
from src.controller.teaching_triggers import TeachingTriggers

triggers = TeachingTriggers(
    master_enabled=True,          # 教学总开关
    eval_current_position=True,   # 当下局面评估
    suggest_moves=True,           # 建议着法推荐
    eval_history_moves=True,      # 历史走法失误预警
    game_over_summary=True,       # 终局复盘总结
)
controller.set_teaching(triggers)
```

---

## 七、AI 综合设置与在线 LLM 接入

### 7.1 持久化结构 (`data/settings.json`)
```json
{
  "persona": "你的自定义女仆人设...",
  "llm": {
    "api_base": "https://api.deepseek.com",
    "api_key": "sk-...",
    "model": "deepseek-chat",
    "reasoning_effort": "auto",
    "stream": true,
    "show_tool_records": false,
    "search_api_url": "",
    "search_api_key": ""
  }
}
```

### 7.2 支持的服务提供商
- **DeepSeek**：`https://api.deepseek.com` (模型：`deepseek-chat` / `deepseek-reasoner`)
- **OpenAI**：`https://api.openai.com/v1` (模型：`gpt-4o`, `gpt-4o-mini`, `o1`)
- **Ollama 本地服务**：`http://localhost:11434` (免 API Key，支持本地模型列表一键拉取)
- **vLLM / LM Studio / OneAPI**：填写标准 OpenAI 兼容端点即可。

---

## 八、网络双人联机服务配置

位于 `src/controller/online_match.py`：
- 支持内置轻量 WebSocket 服务端（默认绑定端口 `8765`）。
- 房主默认仅绑定 `127.0.0.1`（仅本机可连）；如需局域网对战，可在对话框「监听绑定 IP」中显式改为 `0.0.0.0`（服务无鉴权，请注意网络安全），客方输入房主局域网 IP / 端口即可联机。
