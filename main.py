#!/usr/bin/env python3
"""
ChessMaidBot 应用程序启动入口

LLM 配置通过环境变量读取 (见 src/agents/llm_agent.py 文档):
  LLM_API_BASE, LLM_API_KEY, LLM_MODEL, LLM_TIMEOUT, LLM_MAX_TOKENS
未配置 API Key 时, LLMAgent 自动降级为本地描述性回复, 不影响程序运行。
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from src.agents.llm_agent import LLMAgent
from src.config import DEFAULT_MAID_PERSONA
from src.gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ChessMaidBot")
    app.setOrganizationName("ChessMaidBot Team")

    # 创建 LLMAgent, 从环境变量读取 API 配置
    agent = LLMAgent(persona_prompt=DEFAULT_MAID_PERSONA)
    window = MainWindow(agent=agent)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
