"""
走法历史记谱面板 (模块1 - GUI)
纯渲染组件: 从 core 的 MoveRecord 列表整表重建, 不维护自身状态
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt

from ..core.game_record import MoveRecord

class MoveHistoryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["#", "白方 (White)", "黑方 (Black)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
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

        layout.addWidget(self.table)

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

