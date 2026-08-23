#!/usr/bin/env python3
"""
ChessMaidBot 应用程序启动入口
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from src.gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ChessMaidBot")
    app.setOrganizationName("ChessMaidBot Team")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
