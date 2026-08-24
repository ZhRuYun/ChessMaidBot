"""
控制栏与状态栏控件 (模块1 - GUI)
包含模式选择、目标 Elo/难度调节、新局/悔棋/翻转/认输/求和/导出棋局状态功能
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QComboBox, QSpinBox, QFrame
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
    import_state_requested = Signal()   # 导入 PGN/FEN
    export_state_requested = Signal()
    llm_config_requested = Signal()   # 打开 AI 设置对话框 (含教学触发器与人设)
    theme_changed = Signal(str)       # 主题切换 ("跟随系统", "浅色", "深色")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ControlBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # 1. 模式选择下拉框
        mode_label = QLabel("模式:")
        mode_label.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 13px;")
        self.mode_combo = QComboBox(self)
        self.mode_combo.addItems([MODE_LABELS[mode] for mode in GameMode])
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e222d;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 500;
            }
            QComboBox:hover {
                border-color: #475569;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e222d;
                color: #f1f5f9;
                selection-background-color: #3b82f6;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

        # 2. Stockfish Elo 档位预设与微调
        self.elo_label = QLabel("难度:")
        self.elo_label.setStyleSheet("color: #fbbf24; font-weight: 600; font-size: 13px;")
        
        self.elo_preset_combo = QComboBox(self)
        self.elo_preset_combo.addItems(["新手 (500)", "业余 (1000)", "职业 (1500)", "大师 (2000)", "特级大师 (2500)", "自定义"])
        self.elo_preset_combo.setCurrentIndex(2) # 默认职业 1500
        self.elo_preset_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e222d;
                color: #fbbf24;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 12px;
                font-weight: 500;
            }
            QComboBox:hover { border-color: #475569; }
            QComboBox::drop-down { border: none; width: 18px; }
            QComboBox QAbstractItemView {
                background-color: #1e222d;
                color: #fbbf24;
                selection-background-color: #3b82f6;
                border: 1px solid #334155;
            }
        """)
        self.elo_preset_combo.currentTextChanged.connect(self._on_elo_preset_changed)

        self.elo_spin = QSpinBox(self)
        self.elo_spin.setRange(STOCKFISH_MIN_ELO, STOCKFISH_MAX_ELO)
        self.elo_spin.setSingleStep(50)
        self.elo_spin.setValue(STOCKFISH_DEFAULT_ELO)
        self.elo_spin.setStyleSheet("""
            QSpinBox {
                background-color: #1e222d;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: 500;
            }
            QSpinBox:hover {
                border-color: #475569;
            }
        """)
        self.elo_spin.valueChanged.connect(self.elo_changed.emit)

        # 分割线
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: #334155;")

        # 3. 对局控制按钮组 (极简现代扁平风格)
        self.btn_new_game = QPushButton("新局")
        self.btn_undo = QPushButton("悔棋")
        self.btn_flip = QPushButton("翻转")
        self.btn_draw = QPushButton("求和")
        self.btn_resign = QPushButton("认输")

        # 导入/导出棋局状态按钮
        self.btn_import_state = QPushButton("导入 (PGN/FEN)")
        self.btn_export_state = QPushButton("导出 (PGN+FEN)")

        # AI 设置按钮
        self.btn_llm_config = QPushButton("AI 设置")

        # 主题切换下拉框
        theme_label = QLabel("主题:")
        theme_label.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 13px;")
        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(["跟随系统", "浅色", "深色"])
        self.theme_combo.setStyleSheet(self.mode_combo.styleSheet())
        self.theme_combo.currentTextChanged.connect(self.theme_changed.emit)

        standard_buttons = [
            self.btn_new_game, self.btn_undo, self.btn_flip, self.btn_draw
        ]

        for btn in standard_buttons:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e222d;
                    color: #e2e8f0;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #282f3e;
                    color: #ffffff;
                    border-color: #60a5fa;
                }
                QPushButton:pressed {
                    background-color: #1a1e28;
                }
            """)

        self.btn_resign.setStyleSheet("""
            QPushButton {
                background-color: #31181e;
                color: #fca5a5;
                border: 1px solid #5c242e;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #451d27;
                color: #ffffff;
                border-color: #ef4444;
            }
            QPushButton:pressed {
                background-color: #261217;
            }
        """)

        btn_action_style = """
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: #ffffff;
                border-color: #38bdf8;
            }
            QPushButton:pressed {
                background-color: #075985;
            }
        """
        self.btn_import_state.setStyleSheet(btn_action_style)
        self.btn_export_state.setStyleSheet(btn_action_style)

        # AI 设置按钮样式
        self.btn_llm_config.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #a78bfa;
                border: 1px solid #6d28d9;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #6d28d9;
                color: #ffffff;
                border-color: #a78bfa;
            }
            QPushButton:pressed {
                background-color: #5b21b6;
            }
        """)

        self.btn_new_game.clicked.connect(self.new_game_requested.emit)
        self.btn_undo.clicked.connect(self.undo_requested.emit)
        self.btn_flip.clicked.connect(self.flip_requested.emit)
        self.btn_draw.clicked.connect(self.draw_requested.emit)
        self.btn_resign.clicked.connect(self.resign_requested.emit)
        self.btn_import_state.clicked.connect(self.import_state_requested.emit)
        self.btn_export_state.clicked.connect(self.export_state_requested.emit)
        self.btn_llm_config.clicked.connect(self.llm_config_requested.emit)

        layout.addWidget(mode_label)
        layout.addWidget(self.mode_combo)
        layout.addWidget(self.elo_label)
        layout.addWidget(self.elo_preset_combo)
        layout.addWidget(self.elo_spin)
        layout.addWidget(sep1)
        layout.addWidget(self.btn_new_game)
        layout.addWidget(self.btn_undo)
        layout.addWidget(self.btn_flip)
        layout.addWidget(self.btn_draw)
        layout.addWidget(self.btn_resign)
        layout.addStretch()
        layout.addWidget(theme_label)
        layout.addWidget(self.theme_combo)
        layout.addWidget(self.btn_llm_config)
        layout.addWidget(self.btn_import_state)
        layout.addWidget(self.btn_export_state)

        self._update_elo_visibility(self.mode_combo.currentText())

    def _on_elo_preset_changed(self, text: str):
        preset_map = {
            "新手 (500)": 500,
            "业余 (1000)": 1000,
            "职业 (1500)": 1500,
            "大师 (2000)": 2000,
            "特级大师 (2500)": 2500,
        }
        if text in preset_map:
            self.elo_spin.blockSignals(True)
            self.elo_spin.setValue(preset_map[text])
            self.elo_spin.blockSignals(False)
            self.elo_changed.emit(preset_map[text])

    def _on_mode_changed(self, text: str):
        self._update_elo_visibility(text)
        self.mode_changed.emit(text)

    def _update_elo_visibility(self, text: str):
        is_vs_engine = MODE_LABELS[GameMode.VS_ENGINE] == text
        self.elo_label.setVisible(is_vs_engine)
        self.elo_preset_combo.setVisible(is_vs_engine)
        self.elo_spin.setVisible(is_vs_engine)
