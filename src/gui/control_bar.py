"""
控制栏与状态栏控件 (模块1 - GUI)
包含模式选择、目标 Elo/难度调节、新局/悔棋/翻转/认输/求和/导出功能
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QComboBox, QSpinBox
)
from PySide6.QtCore import Signal

from ..controller.game_modes import GameMode, MODE_LABELS
from ..config import STOCKFISH_MIN_ELO, STOCKFISH_MAX_ELO, STOCKFISH_DEFAULT_ELO


class ControlBar(QWidget):
    new_game_requested = Signal()
    undo_requested = Signal()
    flip_requested = Signal()
    resign_requested = Signal()
    draw_requested = Signal()
    mode_changed = Signal(str)
    elo_changed = Signal(int)
    export_pgn_requested = Signal()
    export_fen_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)

        # 1. 模式选择下拉框
        mode_label = QLabel("对弈模式:")
        mode_label.setStyleSheet("color: #ccc; font-weight: bold; font-size: 13px;")
        self.mode_combo = QComboBox(self)
        self.mode_combo.addItems([MODE_LABELS[mode] for mode in GameMode])
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #2b2b38;
                color: #fff;
                border: 1px solid #4f4f66;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 12px;
            }
        """)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

        # 2. Stockfish 目标 Elo 设定微调框
        self.elo_label = QLabel("引擎 Elo:")
        self.elo_label.setStyleSheet("color: #ffa726; font-weight: bold; font-size: 12px;")
        self.elo_spin = QSpinBox(self)
        self.elo_spin.setRange(STOCKFISH_MIN_ELO, STOCKFISH_MAX_ELO)
        self.elo_spin.setSingleStep(50)
        self.elo_spin.setValue(STOCKFISH_DEFAULT_ELO)
        self.elo_spin.setStyleSheet("""
            QSpinBox {
                background-color: #2b2b38;
                color: #fff;
                border: 1px solid #4f4f66;
                border-radius: 5px;
                padding: 3px 6px;
                font-size: 12px;
            }
        """)
        self.elo_spin.valueChanged.connect(self.elo_changed.emit)

        # 3. 对局控制按钮组
        self.btn_new_game = QPushButton("🆕 新对局")
        self.btn_undo = QPushButton("↩️ 悔棋")
        self.btn_flip = QPushButton("🔄 翻转")
        self.btn_draw = QPushButton("🤝 求和")
        self.btn_resign = QPushButton("🏳️ 认输")
        self.btn_export_pgn = QPushButton("📋 PGN")
        self.btn_export_fen = QPushButton("🏷️ FEN")

        buttons = [
            self.btn_new_game, self.btn_undo, self.btn_flip,
            self.btn_draw, self.btn_resign, self.btn_export_pgn, self.btn_export_fen
        ]

        for btn in buttons:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #333345;
                    color: #e0e0e0;
                    border: 1px solid #4a4a60;
                    border-radius: 5px;
                    padding: 5px 9px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #44445c;
                    color: white;
                    border: 1px solid #64b5f6;
                }
            """)

        self.btn_resign.setStyleSheet("""
            QPushButton {
                background-color: #4a2828;
                color: #ffcccc;
                border: 1px solid #773333;
                border-radius: 5px;
                padding: 5px 9px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #663333;
                color: white;
                border: 1px solid #ff5555;
            }
        """)

        self.btn_new_game.clicked.connect(self.new_game_requested.emit)
        self.btn_undo.clicked.connect(self.undo_requested.emit)
        self.btn_flip.clicked.connect(self.flip_requested.emit)
        self.btn_draw.clicked.connect(self.draw_requested.emit)
        self.btn_resign.clicked.connect(self.resign_requested.emit)
        self.btn_export_pgn.clicked.connect(self.export_pgn_requested.emit)
        self.btn_export_fen.clicked.connect(self.export_fen_requested.emit)

        layout.addWidget(mode_label)
        layout.addWidget(self.mode_combo)
        layout.addWidget(self.elo_label)
        layout.addWidget(self.elo_spin)
        layout.addWidget(self.btn_new_game)
        layout.addWidget(self.btn_undo)
        layout.addWidget(self.btn_flip)
        layout.addWidget(self.btn_draw)
        layout.addWidget(self.btn_resign)
        layout.addStretch()
        layout.addWidget(self.btn_export_pgn)
        layout.addWidget(self.btn_export_fen)

        self._update_elo_visibility(self.mode_combo.currentText())

    def _on_mode_changed(self, text: str):
        self._update_elo_visibility(text)
        self.mode_changed.emit(text)

    def _update_elo_visibility(self, text: str):
        is_vs_engine = MODE_LABELS[GameMode.VS_ENGINE] == text
        self.elo_label.setVisible(is_vs_engine)
        self.elo_spin.setVisible(is_vs_engine)

