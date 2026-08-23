"""
走法历史记谱面板 (Move History Table Panel)
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt

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
                background-color: #2b2b2b;
                color: #e0e0e0;
                gridline-color: #3e3e3e;
                font-family: "Segoe UI", "Consolas", sans-serif;
                font-size: 13px;
                border: 1px solid #3e3e3e;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #1e1e1e;
                color: #aaa;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #333;
            }
            QTableWidget::item:selected {
                background-color: #3d5a80;
                color: white;
            }
        """)

        layout.addWidget(self.table)

    def add_move(self, san: str, is_white: bool):
        """向记谱表添加一步走法"""
        if is_white:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            
            num_item = QTableWidgetItem(f"{row_idx + 1}.")
            num_item.setTextAlignment(Qt.AlignCenter)
            white_item = QTableWidgetItem(san)
            white_item.setTextAlignment(Qt.AlignCenter)
            black_item = QTableWidgetItem("")
            black_item.setTextAlignment(Qt.AlignCenter)
            
            self.table.setItem(row_idx, 0, num_item)
            self.table.setItem(row_idx, 1, white_item)
            self.table.setItem(row_idx, 2, black_item)
        else:
            row_idx = self.table.rowCount() - 1
            if row_idx >= 0:
                black_item = QTableWidgetItem(san)
                black_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, 2, black_item)
        
        self.table.scrollToBottom()

    def clear(self):
        """清空走法记录"""
        self.table.setRowCount(0)

    def undo_last_move(self):
        """撤销最后一步记谱"""
        row_count = self.table.rowCount()
        if row_count == 0:
            return
        last_row = row_count - 1
        black_item = self.table.item(last_row, 2)
        if black_item and black_item.text().strip():
            black_item.setText("")
        else:
            self.table.removeRow(last_row)
