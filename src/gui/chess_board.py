"""
交互式棋盘控件 (模块1 - GUI)
- 高清矢量直绘, 支持鼠标拖拽与点击落子, Lichess 风格王车易位
- 只读使用 BoardState 做规则查询; 走法经 move_ready 信号交由调度层应用
"""
from typing import Optional, Dict, List
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, QPoint, QPointF, Signal
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPixmap, QFont
)
from PySide6.QtSvg import QSvgRenderer
import chess

from ..config import (
    BOARD_THEME, DEFAULT_SQUARE_SIZE, PIECES_DIR
)
from ..core.board_state import BoardState
from .promotion_dialog import PromotionDialog

class ChessBoardWidget(QWidget):
    move_ready = Signal(object)  # chess.Move, 由调度层应用

    def __init__(self, board_state: BoardState, parent=None):
        super().__init__(parent)
        self.board_state = board_state
        self.square_size = DEFAULT_SQUARE_SIZE
        self.is_flipped = False

        self.selected_square: Optional[int] = None
        self.legal_destinations: List[int] = []
        self.last_move: Optional[chess.Move] = None
        self.preview_board: Optional[chess.Board] = None # 用于历史步数预览模式

        # 拖拽交互状态
        self.dragging_square: Optional[int] = None
        self.drag_current_pos: Optional[QPoint] = None

        # 预渲染高清矢量棋子缓存 (2x 分辨率抗锯齿)
        self.piece_pixmaps: Dict[str, QPixmap] = {}
        self.load_piece_pixmaps()

        # 固定棋盘像素大小
        self.setFixedSize(self.square_size * 8, self.square_size * 8)
        self.setMouseTracking(True)

    def set_preview_board(self, board: Optional[chess.Board], last_move: Optional[chess.Move] = None):
        """设置预览棋盘（用于回看历史局面）"""
        self.preview_board = board
        self.last_move = last_move
        self.selected_square = None
        self.legal_destinations.clear()
        self.update()

    def get_current_display_board(self) -> chess.Board:
        return self.preview_board if self.preview_board is not None else self.board_state.board

    def load_piece_pixmaps(self):
        """将 SVG 棋子渲染为高清 Pixmap (双倍采样，极其锐利)"""
        render_size = self.square_size * 2
        symbols = ['P', 'N', 'B', 'R', 'Q', 'K']
        for color_prefix in ['w', 'b']:
            for sym in symbols:
                key = f"{color_prefix}{sym}"
                svg_path = str(PIECES_DIR / f"{key}.svg")
                renderer = QSvgRenderer(svg_path)

                pix = QPixmap(render_size, render_size)
                pix.fill(Qt.transparent)

                painter = QPainter(pix)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setRenderHint(QPainter.SmoothPixmapTransform)
                renderer.render(painter)
                painter.end()

                self.piece_pixmaps[key] = pix

    def flip_board(self):
        """翻转棋盘视角"""
        self.is_flipped = not self.is_flipped
        self.update()

    def show_move(self, move: Optional[chess.Move]):
        """调度层确认走法后刷新上步高亮并重绘"""
        self.preview_board = None
        self.last_move = move
        self.update()

    def reset_view(self):
        """新对局时清空选中和高亮"""
        self.preview_board = None
        self.selected_square = None
        self.legal_destinations.clear()
        self.last_move = None
        self.update()

    def square_to_col_row(self, square: int) -> tuple[int, int]:
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if self.is_flipped:
            col = 7 - file
            row = rank
        else:
            col = file
            row = 7 - rank
        return col, row

    def pos_to_square(self, pos: QPoint) -> Optional[int]:
        col = pos.x() // self.square_size
        row = pos.y() // self.square_size
        if 0 <= col < 8 and 0 <= row < 8:
            if self.is_flipped:
                file = 7 - col
                rank = row
            else:
                file = col
                rank = 7 - row
            return chess.square(file, rank)
        return None

    def _event_pos(self, event) -> QPoint:
        pos = event.position() if isinstance(event.position(), QPointF) else event.pos()
        return pos.toPoint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 1. 绘制 8x8 格子背景
        for rank in range(8):
            for file in range(8):
                sq = chess.square(file, rank)
                col, row = self.square_to_col_row(sq)
                x = col * self.square_size
                y = row * self.square_size
                is_light = (file + rank) % 2 != 0
                bg_color = QColor(BOARD_THEME["light_square"] if is_light else BOARD_THEME["dark_square"])
                painter.fillRect(x, y, self.square_size, self.square_size, bg_color)

                # 坐标文字标注
                font = QFont("Segoe UI", 9, QFont.Bold)
                painter.setFont(font)
                if row == 7:
                    file_label = chr(ord('a') + file)
                    painter.setPen(QColor("#888" if is_light else "#edd6b8"))
                    painter.drawText(x + self.square_size - 14, y + self.square_size - 4, file_label)
                if col == 0:
                    rank_label = str(rank + 1)
                    painter.setPen(QColor("#888" if is_light else "#edd6b8"))
                    painter.drawText(x + 3, y + 13, rank_label)

        # 2. 绘制上步走法高亮 (Last move highlight)
        if self.last_move:
            for sq in [self.last_move.from_square, self.last_move.to_square]:
                col, row = self.square_to_col_row(sq)
                hl_color = QColor(BOARD_THEME["highlight_last_move"])
                hl_color.setAlpha(150)
                painter.fillRect(col * self.square_size, row * self.square_size, self.square_size, self.square_size, hl_color)

        # 3. 绘制将军红色警示 (Check alert)
        disp_board = self.get_current_display_board()
        if disp_board.is_check():
            king_sq = disp_board.king(disp_board.turn)
            if king_sq is not None:
                col, row = self.square_to_col_row(king_sq)
                chk_color = QColor(BOARD_THEME["highlight_check"])
                chk_color.setAlpha(180)
                painter.fillRect(col * self.square_size, row * self.square_size, self.square_size, self.square_size, chk_color)

        # 4. 绘制当前选中格子高亮
        if self.selected_square is not None and self.preview_board is None:
            c, r = self.square_to_col_row(self.selected_square)
            sel_color = QColor(BOARD_THEME["highlight_selected"])
            sel_color.setAlpha(160)
            painter.fillRect(c * self.square_size, r * self.square_size, self.square_size, self.square_size, sel_color)

        # 5. 绘制所有未被拖拽的棋子
        for sq in range(64):
            if sq == self.dragging_square:
                continue  # 正在拖拽的棋子稍后置顶绘制
            piece = disp_board.piece_at(sq)
            if piece:
                col, row = self.square_to_col_row(sq)
                color_prefix = "w" if piece.color == chess.WHITE else "b"
                key = f"{color_prefix}{piece.symbol().upper()}"
                pix = self.piece_pixmaps.get(key)
                if pix:
                    target_rect = QRect(col * self.square_size, row * self.square_size, self.square_size, self.square_size)
                    painter.drawPixmap(target_rect, pix)

        # 6. 绘制合法走法提示点与吃子环 (覆盖在棋子或空格上)
        if self.selected_square is not None and self.preview_board is None:
            for dest_sq in self.legal_destinations:
                dc, dr = self.square_to_col_row(dest_sq)
                cx = dc * self.square_size + self.square_size // 2
                cy = dr * self.square_size + self.square_size // 2

                target_piece = self.board_state.get_piece_at(dest_sq)
                # 检查是否为吃子（或者是易位指向的车）
                is_castling_rook = False
                sel_piece = self.board_state.get_piece_at(self.selected_square)
                if sel_piece and sel_piece.piece_type == chess.KING and target_piece and target_piece.piece_type == chess.ROOK:
                    is_castling_rook = True

                if target_piece and not is_castling_rook:
                    # 吃子高亮指示环 (红绿醒目高亮微调)
                    pen = QPen(QColor(180, 50, 50, 180), 5)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    radius = self.square_size // 2 - 4
                    painter.drawEllipse(QPoint(cx, cy), radius, radius)
                elif is_castling_rook:
                    # 易位车圆环指示
                    pen = QPen(QColor(37, 99, 235, 180), 5)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    radius = self.square_size // 2 - 4
                    painter.drawEllipse(QPoint(cx, cy), radius, radius)
                else:
                    # 空地落子指示圆点
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(QColor(40, 120, 40, 90)))
                    painter.drawEllipse(QPoint(cx, cy), 13, 13)

        # 7. 置顶绘制正在拖拽中的棋子 (跟随鼠标中心)
        if self.dragging_square is not None and self.drag_current_pos is not None:
            piece = self.board_state.get_piece_at(self.dragging_square)
            if piece:
                color_prefix = "w" if piece.color == chess.WHITE else "b"
                key = f"{color_prefix}{piece.symbol().upper()}"
                pix = self.piece_pixmaps.get(key)
                if pix:
                    half = self.square_size // 2
                    drag_rect = QRect(
                        self.drag_current_pos.x() - half,
                        self.drag_current_pos.y() - half,
                        self.square_size,
                        self.square_size
                    )
                    painter.drawPixmap(drag_rect, pix)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        # 如果处于历史局面预览模式，点击任意位置切回当前实时局面
        if self.preview_board is not None:
            self.preview_board = None
            self.last_move = self.board_state.last_move
            self.update()
            return

        if self.board_state.is_game_over():
            return
        sq = self.pos_to_square(self._event_pos(event))
        if sq is None:
            return

        # 如果当前已选中一个棋子，且点击了合法目的地，直接执行移动
        if self.selected_square is not None and sq in self.legal_destinations:
            self.execute_user_move(self.selected_square, sq)
            return

        # 选中自己阵营的棋子
        piece = self.board_state.get_piece_at(sq)
        if piece and piece.color == self.board_state.turn:
            self.selected_square = sq
            self.dragging_square = sq
            self.drag_current_pos = self._event_pos(event)
            self._compute_legal_destinations(sq)
            self.update()
        else:
            self._clear_selection()

    def mouseMoveEvent(self, event):
        if self.dragging_square is not None:
            self.drag_current_pos = self._event_pos(event)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging_square is not None:
            from_sq = self.dragging_square
            to_sq = self.pos_to_square(self._event_pos(event))

            self.dragging_square = None
            self.drag_current_pos = None

            if to_sq is not None and to_sq != from_sq and to_sq in self.legal_destinations:
                self.execute_user_move(from_sq, to_sq)
            else:
                self.update()

    def _clear_selection(self):
        self.selected_square = None
        self.legal_destinations.clear()
        self.dragging_square = None
        self.drag_current_pos = None
        self.update()

    def _compute_legal_destinations(self, from_sq: int):
        """计算合法目标格（包含王车易位时点击目标车）"""
        self.legal_destinations.clear()
        piece = self.board_state.get_piece_at(from_sq)
        if not piece:
            return

        for m in self.board_state.get_legal_moves_from(from_sq):
            self.legal_destinations.append(m.to_square)
            # 如果是王车易位，同时把对应车的位置加入合法目的地（Lichess交互）
            if piece.piece_type == chess.KING:
                if piece.color == chess.WHITE:
                    if m.to_square == chess.G1:
                        self.legal_destinations.append(chess.H1)
                    elif m.to_square == chess.C1:
                        self.legal_destinations.append(chess.A1)
                else:
                    if m.to_square == chess.G8:
                        self.legal_destinations.append(chess.H8)
                    elif m.to_square == chess.C8:
                        self.legal_destinations.append(chess.A8)

    def execute_user_move(self, from_sq: int, to_sq: int):
        """解析用户意图 (升变/易位), 生成 chess.Move 交调度层应用"""
        promotion_piece = None
        if self.board_state.is_promotion_move(from_sq, to_sq):
            dialog = PromotionDialog(self.board_state.turn, self)
            if dialog.exec():
                promotion_piece = dialog.selected_piece_type
            else:
                self._clear_selection()
                return

        move = self.board_state.resolve_castling_or_normal_move(from_sq, to_sq, promotion_piece)
        if move is None:
            self._clear_selection()
            return

        self.selected_square = None
        self.legal_destinations.clear()
        self.move_ready.emit(move)
