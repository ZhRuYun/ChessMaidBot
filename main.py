#!/usr/bin/env python3
"""
ChessMaidBot 应用程序启动入口

LLM 配置通过持久化 settings.json 与环境变量读取:
  未配置 API Key 时, LLMAgent 自动降级为本地描述性回复, 不影响程序运行。
启动时自动检查 Stockfish 引擎与 Lichess 开局数据库是否完备，缺失时自动安装补齐。
"""
import logging
import sys
from PySide6.QtWidgets import QApplication

from src.config import ENGINE_PATH, DEFAULT_OPENINGS_JSON_PATH
from src.gui.main_window import MainWindow

# 统一日志初始化: 全模块可观测 (LLM 失败/降级/缓存命中/用量等关键事件均落日志)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def ensure_assets_ready():
    """检查引擎与开局库资产，如缺失则自动安装 Stockfish 引擎与 Lichess 开局库"""
    from scripts.download_assets import is_valid_stockfish_binary, setup_openings_database, setup_stockfish
    needs_engine = not is_valid_stockfish_binary(ENGINE_PATH)
    needs_openings = not DEFAULT_OPENINGS_JSON_PATH.exists() or DEFAULT_OPENINGS_JSON_PATH.stat().st_size < 1000

    if needs_openings or needs_engine:
        try:
            print("[INFO] 正在检测并自动安装 Stockfish 引擎与 Lichess 开局库...")
            if needs_openings:
                setup_openings_database()
            if needs_engine:
                setup_stockfish()
        except Exception as e:
            print(f"[WARN] 自动安装资源过程提示: {e}")


def main():
    ensure_assets_ready()

    app = QApplication(sys.argv)
    app.setApplicationName("ChessMaidBot")
    app.setOrganizationName("ChessMaidBot Team")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
