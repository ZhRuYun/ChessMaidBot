"""
走法历史记谱面板 (模块1 - GUI)
纯渲染组件: 从 core 的 MoveRecord 列表整表重建, 并提供 lichess 风格的步数导航控制栏
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton
)
from PySide6.QtCore import Qt, Signal

from ..core.game_record import MoveRecord

class MoveHistoryPanel(QWidget):
    # 导航信号: 回到第一步(-2), 上一步(-1), 下一步(1), 最后一步(2)
    nav_first_requested = Signal()
    nav_prev_requested = Signal()
    nav_next_requested = Signal()
    nav_last_requested = Signal()
    move_selected = Signal(int, int) # (row, col) 点击特定着法

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["#", "白方 (White)", "黑方 (Black)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0f172a;
                color: #e2e8f0;
                gridline-color: #1e293b;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
                font-size: 13px;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                font-weight: 600;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #334155;
            }
            QTableWidget::item:selected {
                background-color: #1e3a8a;
                color: #ffffff;
            }
        """)
        self.table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

        # Lichess 风格步数导航工具条: |<  <  >  >|
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(4)
        self.btn_first = QPushButton("|<")
        self.btn_prev = QPushButton("<")
        self.btn_next = QPushButton(">")
        self.btn_last = QPushButton(">|")

        btn_style = """
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
                padding: 4px 0px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
                border-color: #38bdf8;
            }
            QPushButton:pressed {
                background-color: #0f172a;
            }
        """
        for b in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            b.setStyleSheet(btn_style)
            b.setFixedHeight(28)
            nav_layout.addWidget(b)

        self.btn_first.clicked.connect(self.nav_first_requested.emit)
        self.btn_prev.clicked.connect(self.nav_prev_requested.emit)
        self.btn_next.clicked.connect(self.nav_next_requested.emit)
        self.btn_last.clicked.connect(self.nav_last_requested.emit)

        layout.addLayout(nav_layout)

    def _on_cell_clicked(self, row: int, col: int):
        if col in (1, 2):
            self.move_selected.emit(row, col)

    def set_records(self, records: list):
        """以核心记谱数据整表重建 (单一数据源, 悔棋/导入/重开均正确)"""
        self.table.setRowCount(0)
        for record in records:
            self._append_record(record)
        self.table.scrollToBottom()

    def _append_record(self, record: MoveRecord):
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)

        num_item = QTableWidgetItem(f"{record.move_number}.")
        num_item.setTextAlignment(Qt.AlignCenter)
        white_item = QTableWidgetItem(record.white_san)
        white_item.setTextAlignment(Qt.AlignCenter)
        black_item = QTableWidgetItem(record.black_san)
        black_item.setTextAlignment(Qt.AlignCenter)

        self.table.setItem(row_idx, 0, num_item)
        self.table.setItem(row_idx, 1, white_item)
        self.table.setItem(row_idx, 2, black_item)

    def clear(self):
        self.table.setRowCount(0)

    def apply_theme(self, is_light: bool):
        """适配浅色/深色主题"""
        if is_light:
            self.table.setStyleSheet("""
                QTableWidget {
                    background-color: #ffffff;
                    color: #0f172a;
                    gridline-color: #e2e8f0;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    font-size: 13px;
                }
                QHeaderView::section {
                    background-color: #f1f5f9;
                    color: #475569;
                    font-weight: 600;
                    border: none;
                    border-bottom: 1px solid #cbd5e1;
                    padding: 4px;
                }
                QTableWidget::item:selected {
                    background-color: #bfdbfe;
                    color: #1e3a8a;
                    font-weight: 700;
                }
            """)
        else:
            self.table.setStyleSheet("""
                QTableWidget {
                    background-color: #0f172a;
                    color: #e2e8f0;
                    gridline-color: #1e293b;
                    border: 1px solid #1e293b;
                    border-radius: 6px;
                    font-size: 13px;
                }
                QHeaderView::section {
                    background-color: #1e293b;
                    color: #94a3b8;
                    font-weight: 600;
                    border: none;
                    border-bottom: 1px solid #334155;
                    padding: 4px;
                }
                QTableWidget::item:selected {
                    background-color: #2563eb;
                    color: #ffffff;
                    font-weight: 700;
                }
            """)

