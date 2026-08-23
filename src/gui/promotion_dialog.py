"""
升变选择对话框 (Pawn Promotion Dialog) - 高清矢量支持
"""
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
import chess
from ..config import PIECES_DIR

class PromotionDialog(QDialog):
    def __init__(self, color: chess.Color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("兵的升变选择")
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setStyleSheet("background-color: #2b2b36; color: white;")
        self.selected_piece_type = chess.QUEEN

        color_prefix = "w" if color == chess.WHITE else "b"
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        pieces = [
            ("Q", chess.QUEEN, "后 (Queen)"),
            ("R", chess.ROOK, "车 (Rook)"),
            ("B", chess.BISHOP, "象 (Bishop)"),
            ("N", chess.KNIGHT, "马 (Knight)")
        ]

        for symbol, p_type, tooltip in pieces:
            btn = QPushButton(self)
            btn.setToolTip(tooltip)
            btn.setFixedSize(72, 72)
            btn.setIconSize(QSize(60, 60))
            
            svg_path = str(PIECES_DIR / f"{color_prefix}{symbol}.svg")
            renderer = QSvgRenderer(svg_path)
            pix = QPixmap(120, 120)
            pix.fill(Qt.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing)
            renderer.render(painter)
            painter.end()

            btn.setIcon(QIcon(pix))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b3b4d;
                    border: 2px solid #555566;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #4f4f66;
                    border: 2px solid #64b5f6;
                }
            """)
            btn.clicked.connect(lambda _, pt=p_type: self._on_select(pt))
            layout.addWidget(btn)

    def _on_select(self, piece_type: chess.PieceType):
        self.selected_piece_type = piece_type
        self.accept()
