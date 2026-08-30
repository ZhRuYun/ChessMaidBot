#!/usr/bin/env python3
"""
ChessMaidBot 应用程序启动入口

LLM 配置通过持久化 settings.json 与环境变量读取:
  未配置 API Key 时, LLMAgent 自动降级为本地描述性回复, 不影响程序运行。
启动时自动检查 Stockfish 引擎与开局/战术/残局数据库是否完备，缺失时自动补齐。
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from src.config import ENGINE_PATH, DEFAULT_OPENINGS_JSON_PATH, DEFAULT_TACTICS_PATH
from src.gui.main_window import MainWindow


def ensure_assets_ready():
    """检查引擎与数据库资产，如缺失则自动执行初始化脚本"""
    from scripts.download_assets import is_valid_stockfish_binary, setup_databases, setup_stockfish
    needs_setup = False

    # 检查引擎
    if not is_valid_stockfish_binary(ENGINE_PATH):
        needs_setup = True

    # 检查数据库
    if not DEFAULT_OPENINGS_JSON_PATH.exists() or not DEFAULT_TACTICS_PATH.exists():
        needs_setup = True

    if needs_setup:
        try:
            print("[INFO] 正在检测并自动补齐引擎与数据库资源...")
            setup_databases()
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
