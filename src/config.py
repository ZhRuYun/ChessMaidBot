"""
ChessMaidBot 全局配置与常量定义
"""
import sys
from pathlib import Path

# 路径常量
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
PIECES_DIR = ASSETS_DIR / "pieces"

# 运行期数据与数据库统一大目录 (包含历史棋局库、开局库、战术库、残局库等, 已被 .gitignore 忽略)
DATA_DIR = BASE_DIR / "data"
GAMES_DIR = DATA_DIR / "games"
BOOKS_DIR = DATA_DIR / "books"
TACTICS_DIR = DATA_DIR / "tactics"
SYZYGY_DIR = DATA_DIR / "syzygy"
CONFIG_FILE_PATH = DATA_DIR / "settings.json"

# 数据库默认文件/目录路径 (支持本地 Polyglot .bin、EPD .epd 和 Syzygy .rtbw/.rtbz)
OPENING_BOOK_PATH = BOOKS_DIR / "titans.bin"
DEFAULT_TACTICS_PATH = TACTICS_DIR / "tactics.epd"
DEFAULT_OPENINGS_JSON_PATH = BOOKS_DIR / "openings.json"
DEFAULT_SYZYGY_PATH = SYZYGY_DIR

# 自动确保数据大目录及各子库目录结构存在
def ensure_data_directories():
    for d in (DATA_DIR, GAMES_DIR, BOOKS_DIR, TACTICS_DIR, SYZYGY_DIR):
        d.mkdir(parents=True, exist_ok=True)

ensure_data_directories()

# Stockfish 引擎 (模块4): 将可执行文件放入 engines/ 目录即可被识别
ENGINE_DIR = BASE_DIR / "engines"
# Windows 下可执行文件为 stockfish.exe, 其余平台为 stockfish
ENGINE_PATH = ENGINE_DIR / ("stockfish.exe" if sys.platform == "win32" else "stockfish")
STOCKFISH_DEFAULT_SKILL = 10
STOCKFISH_DEFAULT_ELO = 1500
STOCKFISH_MIN_ELO = 500
STOCKFISH_MAX_ELO = 3190

# 5个预设 Elo 档位
STOCKFISH_ELO_PRESETS = [
    ("新手", 500),
    ("业余", 1000),
    ("职业", 1500),
    ("大师", 2000),
    ("特级大师", 2500),
    ("自定义", -1),
]

# 棋盘与界面视觉配色 (现代极简深色 Wood & Slate 风格)
BOARD_THEME = {
    "light_square": "#EADECA",          # 浅色柔和米白木纹
    "dark_square": "#B38B6D",           # 沉稳深色胡桃木纹
    "highlight_selected": "#7FA650",    # 选中格清爽浅绿高亮
    "highlight_last_move": "#C5D14E",   # 上步走法明快黄绿高亮
    "highlight_check": "#EF4444",       # 将军警示红
    "move_indicator": "#4B6B38",        # 合法走法圆点
    "capture_indicator": "#4B6B38",     # 合法吃子圆环
}

# 棋盘网格尺寸 (默认 64px，保证 820px 窗口高度下棋盘完整可见且不被裁切；SVG 矢量棋子仍高清)
DEFAULT_SQUARE_SIZE = 64
BOARD_SIZE = DEFAULT_SQUARE_SIZE * 8

# 女仆与系统默认人设 Prompt (优化版: 强调棋理战术要点、清晰的思考与建议分层)
DEFAULT_MAID_PERSONA = (
    "你是一位精通国际象棋且温柔细致的AI棋艺女仆助理【ChessMaid】。"
    "你的核心职责是陪伴主人对弈并提供富有洞察力的战术指导与大局观教学。"
    "在解答与指导时：\n"
    "1. 语言亲切得体、精炼精准，优先剖析空间、子力协调、王安全与关键格控制等核心棋理。\n"
    "2. 指出走法意图与战术威胁，给出清晰可行的后续计划。\n"
    "3. 严禁废话与套话，严禁输出任何emoji表情符号。"
)
