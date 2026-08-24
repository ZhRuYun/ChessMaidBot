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
├── books/      # Polyglot 格式开局库 (.bin)
├── tactics/    # EPD 战术编码题库 (.epd)
└── syzygy/     # Syzygy 残局库 (.rtbw / .rtbz)
```

### 1.1 自定义开局库 (.bin / .json)
- **文件格式**：标准 Polyglot `.bin` 格式或外置 JSON 开局格式。
- **配置方式**：
  将你的开局库文件放入 `data/books/` 目录下（例如 `titans.bin` 或 `openings.json`）。系统提供了 `python3 scripts/download_assets.py` 一键初始化安装工具。
- **降级机制**：若未放入自定义 `.bin` 文件，系统将自动使用外置或内置开源精选开局库（覆盖王兵、后兵、西西里、西班牙等主流开局）。

### 1.2 自定义战术题库 (.epd)
- **文件格式**：标准 4 字段 EPD 格式（扩展支持 `bm`, `id`, `c0` 等操作码）。
- **配置方式**：
  在 `data/tactics/tactics.epd` 中添加或覆盖自定义 EPD 题库，例如：
  ```epd
  6k1/5ppp/8/8/8/8/1Q4PP/6K1 w - - bm Qb8#; id "mate_in_1"; c0 "底线闷杀";
  ```
- **程序加载**：
  ```python
  from src.database.tactics_db import TacticsDatabase
  tactics_db = TacticsDatabase("data/tactics/my_puzzles.epd")
  ```

### 1.3 自定义 Syzygy 残局库 (.rtbw / .rtbz)
- **配置方式**：将下载的 Syzygy 3-4-5-6 子残局文件放入 `data/syzygy/` 目录。
- **自动挂载**：`EndgameDatabase` 在启动时会自动探测并挂载该目录，提供精准 WDL / DTZ 查询；若不存在则自动降级使用启发式理论残局评估器。

### 1.4 一键下载与环境初始化脚本
项目根目录提供了自动下载与初始化的 Python 脚本：
```bash
python3 scripts/download_assets.py
```
该脚本会自动下载适合当前操作系统的 Stockfish 18 二进制引擎，并初始化开局库与 EPD 战术题库。

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
  STOCKFISH_MIN_ELO = 1320         # 引擎支持的最低 Elo
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

---

## 五、教学触发器配置

通过 `TeachingTriggers` 控制落子自动触发与右侧面板开关：

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

通过继承 `src.agents.base.ChessAgent` 即可快速接入：

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
