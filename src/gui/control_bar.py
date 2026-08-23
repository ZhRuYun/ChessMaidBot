"""
控制栏与状态栏控件 (Control Bar) - 支持 PGN/FEN 统一导出
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QComboBox
)
from PySide6.QtCore import Qt, Signal

class ControlBar(QWidget):
    new_game_requested = Signal()
    undo_requested = Signal()
    flip_requested = Signal()
    mode_changed = Signal(str)
    export_pgn_requested = Signal()
    export_fen_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # 模式选择下拉框
        mode_label = QLabel("对弈模式:")
        mode_label.setStyleSheet("color: #ccc; font-weight: bold; font-size: 13px;")
        self.mode_combo = QComboBox(self)
        self.mode_combo.addItems([
            "本地双人对战 (Local PvP)",
            "人机对弈 (vs Stockfish)",
            "女仆陪练 (vs Maid LLM)"
        ])
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #2b2b38;
                color: #fff;
                border: 1px solid #4f4f66;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 13px;
            }
        """)
        self.mode_combo.currentTextChanged.connect(self.mode_changed.emit)

        # 功能按钮组
        self.btn_new_game = QPushButton("🆕 新对局")
        self.btn_undo = QPushButton("↩️ 悔棋")
        self.btn_flip = QPushButton("🔄 翻转棋盘")
        self.btn_export_pgn = QPushButton("📋 导出PGN")
        self.btn_export_fen = QPushButton("🏷️ 导出FEN")

        for btn in [self.btn_new_game, self.btn_undo, self.btn_flip, self.btn_export_pgn, self.btn_export_fen]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #333345;
                    color: #e0e0e0;
                    border: 1px solid #4a4a60;
                    border-radius: 5px;
                    padding: 6px 12px;
                    font-size: 13px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #44445c;
                    color: white;
                    border: 1px solid #64b5f6;
                }
            """)

        self.btn_new_game.clicked.connect(self.new_game_requested.emit)
        self.btn_undo.clicked.connect(self.undo_requested.emit)
        self.btn_flip.clicked.connect(self.flip_requested.emit)
        self.btn_export_pgn.clicked.connect(self.export_pgn_requested.emit)
        self.btn_export_fen.clicked.connect(self.export_fen_requested.emit)

        layout.addWidget(mode_label)
        layout.addWidget(self.mode_combo)
        layout.addWidget(self.btn_new_game)
        layout.addWidget(self.btn_undo)
        layout.addWidget(self.btn_flip)
        layout.addStretch()
        layout.addWidget(self.btn_export_pgn)
        layout.addWidget(self.btn_export_fen)
