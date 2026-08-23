"""
ChessMaidBot 全局配置与常量定义
"""
from pathlib import Path

# 路径常量
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
PIECES_DIR = ASSETS_DIR / "pieces"

# 运行期数据目录 (历史棋局库等, 已被 .gitignore 忽略)
DATA_DIR = BASE_DIR / "data"
GAMES_DIR = DATA_DIR / "games"

# Stockfish 引擎 (模块4): 将可执行文件放入 engines/ 目录即可被识别
ENGINE_DIR = BASE_DIR / "engines"
ENGINE_PATH = ENGINE_DIR / "stockfish"
STOCKFISH_DEFAULT_SKILL = 10
STOCKFISH_DEFAULT_ELO = 1500
STOCKFISH_MIN_ELO = 1320
STOCKFISH_MAX_ELO = 3190

# 棋盘与界面视觉配色 (Lichess 经典 Wood & Clean 风格)
BOARD_THEME = {
    "light_square": "#F0D9B5",          # 浅色木纹格
    "dark_square": "#B58863",           # 深色木纹格
    "highlight_selected": "#829769",    # 选中格原色高亮
    "highlight_last_move": "#CDD26A",   # 上步走法明亮高亮
    "highlight_check": "#E05353",       # 将军红色警示
    "move_indicator": "#5B7444",        # 合法走法圆点 (半透明由 Alpha 控制)
    "capture_indicator": "#5B7444",     # 合法吃子圆环
}

# 棋盘网格尺寸 (默认 80px，支持高分屏高清矢量直绘)
DEFAULT_SQUARE_SIZE = 80
BOARD_SIZE = DEFAULT_SQUARE_SIZE * 8

# 女仆与系统默认人设 Prompt
DEFAULT_MAID_PERSONA = (
    "你是一位精通国际象棋且温柔细致的AI棋艺女仆助理【ChessMaid】。"
    "你的任务是陪伴主人对弈并学习国际象棋。"
    "在主人走棋时，给予鼓励；在遇到关键战术时，用生动易懂的棋理解释背后的战略目的。"
    "保持礼貌、体贴且专业的语气。"
)
