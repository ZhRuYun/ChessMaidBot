# ChessMaidBot 自定义配置与二次开发教程

本文档介绍 ChessMaidBot 中所有支持自定义配置的功能模块及其配置方法。

---

## 目录
1. [一、数据库大目录与自定义题库/开局库](#一一数据库大目录与自定义题库开局库)
2. [二、Stockfish 引擎配置与 Elo 调节](#二二stockfish-引擎配置与-elo-调节)
3. [三、女仆人设与 Prompt 自定义](#三三女仆人设与-prompt-自定义)
4. [四、棋盘与界面主题配色](#四四棋盘与界面主题配色)
5. [五、教学触发器配置](#五五教学触发器配置)
6. [六、接入真实在线 LLM（DeepSeek / OpenAI 等）](#六六接入真实在线-llmdeepseek--openai-等)

---

## 一、数据库大目录与自定义题库/开局库

所有数据库资源统一收拢在项目根目录的 `data/` 大目录下进行管理：

```
data/
├── games/      # 自动存放持久化的历史棋局 (.pgn + LLM总结)
└── books/      # 开局库目录 (openings.json / titans.bin)
```

### 1.1 开局库 (Lichess 开源开局库 / Polyglot)
- **文件格式**：来自 [lichess-org/chess-openings](https://github.com/lichess-org/chess-openings) 的开源 JSON 库 (`data/books/openings.json`)，也兼容标准 Polyglot `.bin` 格式。
- **作用**：主要用于识别当前局面的开局名称与 ECO 编码供 LLM 识别与使用，并提供推荐走法与权重。
- **配置与更新方式**：
  直接执行 `python3 scripts/download_assets.py` 即可自动从 Lichess 仓库拉取并构建全部 A~E 卷开局库。

### 1.2 玩家历史游戏库
- **储存标准**：只有玩家正常游玩，以将死对手、被对手将死、认输、同意求和等正常结束游戏的棋局才会存入 `data/games/`。0 步棋局或未开局棋局自动过滤。

### 1.3 一键下载与环境初始化脚本
项目根目录提供了自动下载与初始化的 Python 脚本：
```bash
python3 scripts/download_assets.py
```
该脚本会自动下载适合当前操作系统的 Stockfish 引擎，并下载构建 Lichess 开局库。

---

## 二、Stockfish 引擎配置与 Elo 调节

配置文件位于 `src/config.py`。

### 2.1 引擎路径
- 默认路径：`engines/stockfish`（Windows 上为 `engines/stockfish.exe`）。
- 可在 `src/config.py` 中自定义：
  ```python
  ENGINE_PATH = BASE_DIR / "engines" / "stockfish"
  ```

### 2.2 目标 Elo 评级分与技能等级
- 支持通过界面顶部控制栏微调或通过代码直接控制：
  ```python
  STOCKFISH_DEFAULT_SKILL = 10   # 默认 Skill Level (0 ~ 20)
  STOCKFISH_DEFAULT_ELO = 1500     # 默认目标 Elo 等级分
  STOCKFISH_MIN_ELO = 500          # 引擎支持的最低 Elo (低于 1320 自动映射 Skill Level 降级)
  STOCKFISH_MAX_ELO = 3190         # 引擎支持的最高 Elo
  ```

---

## 三、女仆人设与 Prompt 自定义

在 `src/config.py` 中可直接修改全局女仆人设 `DEFAULT_MAID_PERSONA`：

```python
DEFAULT_MAID_PERSONA = (
    "你是一位精通国际象棋且温柔细致的AI棋艺女仆助理【ChessMaid】。"
    "你的任务是陪伴主人对弈并学习国际象棋。"
    "在主人走棋时，给予鼓励；在遇到关键战术时，用生动易懂的棋理解释背后的战略目的。"
    "保持礼貌、体贴且专业的语气。"
)
```

若需在运行时动态变更人设：
```python
agent.persona_prompt = "你的新人设 Prompt..."
```

---

## 四、棋盘与界面主题配色

在 `src/config.py` 中的 `BOARD_THEME` 字典中自定义配色：

```python
BOARD_THEME = {
    "light_square": "#EADECA",          # 浅色柔和米白格
    "dark_square": "#B38B6D",           # 深色胡桃木纹格
    "highlight_selected": "#7FA650",    # 选中格高亮色
    "highlight_last_move": "#C5D14E",   # 上步走法高亮色
    "highlight_check": "#EF4444",       # 将军警示红
    "move_indicator": "#4B6B38",        # 合法走法圆点
    "capture_indicator": "#4B6B38",     # 合法吃子圆环
}
```

### 棋盘格子尺寸

在 `src/config.py` 顶部常量 `DEFAULT_SQUARE_SIZE`（单位：像素）控制每一格的边长，棋盘总尺寸 = `DEFAULT_SQUARE_SIZE × 8`。该值直接影响中央棋盘的渲染大小与窗口布局：

```python
DEFAULT_SQUARE_SIZE = 64   # 当前默认；80 = 大棋盘(640×640)，64 = 标准棋盘(512×512)
BOARD_SIZE = DEFAULT_SQUARE_SIZE * 8
```

> 调整建议：若发现棋盘底部被窗口裁切（常见于 820px 高度窗口或高 DPI 缩放下），将此值从 `80` 调小为 `64` 即可留出充足余量；反之在小屏上想放大棋盘可调大到 `72~80`。棋子为 SVG 矢量 2x 超采样预渲染，缩放后仍保持高清锐利。

---

## 五、教学触发器配置

通过 `TeachingTriggers` 控制落子自动触发与 AI 综合设置面板开关：

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

## 六、接入真实在线 LLM（DeepSeek / OpenAI 等）

系统支持通过 GUI 界面中的「AI 综合设置」弹窗直接配置，亦支持环境变量或代码接入：

### 6.1 GUI 综合设置与连通性测试
在 GUI 顶部点击「AI 综合设置」即可配置：
- **Base URL**：支持 DeepSeek、OpenAI、Ollama 本地服务等
- **API Key**：支持明文/密文切换，持久化保存于 `data/settings.json`
- **模型选择与拉取**：点击「测试连接并拉取模型」按钮可即时检验网络连通性并自动拉取支持的模型列表供下拉点选
- **思考档位 (Reasoning Effort)**：支持 `auto`、`low`、`medium`、`high`、`max` 与 `none`
- **流式响应**：支持 SSE 流式聚合

### 6.2 代码扩展接入
通过继承 `src.agents.base.ChessAgent` 即可自定义接入：

```python
from src.agents.base import ChessAgent, AgentRequest
import requests

class DeepSeekChessAgent(ChessAgent):
    name = "deepseek_maid"

    def __init__(self, api_key: str, persona_prompt: str = ""):
        super().__init__(persona_prompt)
        self.api_key = api_key

    def reply(self, request: AgentRequest) -> str:
        # 可选使用 request.tools 查询引擎或数据库
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": request.persona_prompt},
                {"role": "user", "content": request.user_message},
            ]
        }
        res = requests.post("https://api.deepseek.com/chat/completions", json=payload, headers=headers)
        return res.json()["choices"][0]["message"]["content"]
```

在启动时传入主窗口：
```python
agent = DeepSeekChessAgent(api_key="your-api-key")
window = MainWindow(agent=agent)
```
