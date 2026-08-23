"""
主窗口 (Main Window) - 包含 PGN/FEN 导出、5级教学开关联动与丝滑棋盘事件
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QMessageBox, QFileDialog, QApplication
)
from PySide6.QtCore import Qt
import chess

from ..core.board_state import BoardState, GameResult
from .chess_board import ChessBoardWidget
from .move_history_panel import MoveHistoryPanel
from .chat_panel import ChatPanel, TeachingConfig
from .control_bar import ControlBar

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChessMaidBot - 国际象棋 AI 女仆教学对弈系统")
        self.resize(1240, 790)
        self.setStyleSheet("background-color: #14141a;")

        self.board_state = BoardState()
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. 顶部控制栏
        self.control_bar = ControlBar(self)
        self.control_bar.new_game_requested.connect(self.on_new_game)
        self.control_bar.undo_requested.connect(self.on_undo)
        self.control_bar.flip_requested.connect(self.on_flip)
        self.control_bar.export_pgn_requested.connect(self.on_export_pgn)
        self.control_bar.export_fen_requested.connect(self.on_export_fen)
        main_layout.addWidget(self.control_bar)

        # 2. 中间核心对弈与教学区 (水平布局)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # 左侧：棋盘区域 + 状态指示
        board_container = QVBoxLayout()
        self.status_bar_label = QLabel("当前行动: 白方 (White)")
        self.status_bar_label.setStyleSheet("color: #f1faee; font-size: 15px; font-weight: bold; padding: 4px;")
        board_container.addWidget(self.status_bar_label)

        self.chess_board = ChessBoardWidget(self.board_state, self)
        self.chess_board.move_made.connect(self.on_move_made)
        self.chess_board.game_status_changed.connect(self.on_game_status_changed)
        board_container.addWidget(self.chess_board)
        content_layout.addLayout(board_container)

        # 中间：走法历史双栏记谱表
        history_container = QVBoxLayout()
        history_title = QLabel("📜 对局记谱 (Move List)")
        history_title.setStyleSheet("color: #bbb; font-weight: bold; font-size: 13px;")
        history_container.addWidget(history_title)

        self.history_panel = MoveHistoryPanel(self)
        self.history_panel.setFixedWidth(230)
        history_container.addWidget(self.history_panel)
        content_layout.addLayout(history_container)

        # 右侧：LLM 女仆互动对话窗口
        chat_container = QVBoxLayout()
        self.chat_panel = ChatPanel(self)
        self.chat_panel.message_sent.connect(self.on_user_chat_message)
        chat_container.addWidget(self.chat_panel)
        content_layout.addLayout(chat_container)

        main_layout.addLayout(content_layout)

    def on_move_made(self, san_str: str, uci_str: str):
        """当用户在棋盘上成功落子"""
        is_white_moved = (self.board_state.turn == chess.BLACK)
        self.history_panel.add_move(san_str, is_white_moved)

        # 更新状态指示标签
        turn_str = "白方 (White)" if self.board_state.turn == chess.WHITE else "黑方 (Black)"
        if self.board_state.is_check():
            self.status_bar_label.setText(f"当前行动: {turn_str} ⚠️ [ 被将军 Check! ]")
            self.status_bar_label.setStyleSheet("color: #ff5252; font-size: 15px; font-weight: bold;")
        else:
            self.status_bar_label.setText(f"当前行动: {turn_str}")
            self.status_bar_label.setStyleSheet("color: #f1faee; font-size: 15px; font-weight: bold;")

        # 检查教学触发器
        cfg = self.chat_panel.teaching_config
        if cfg.master_enabled and cfg.eval_current_position:
            side_cn = "白方" if is_white_moved else "黑方"
            if self.board_state.is_check():
                self.chat_panel.append_maid_message(
                    f"主人，**{side_cn}** 走出了 **`{san_str}`** 并发动了将军！请仔细应对防守哦。"
                )

    def on_game_status_changed(self, status: dict):
        """对局终局判定"""
        if status.get("is_over"):
            reason = status.get("reason", "对局结束")
            result = status.get("result", "")
            cfg = self.chat_panel.teaching_config
            if cfg.master_enabled and cfg.game_over_summary:
                self.chat_panel.append_maid_message(f"🏁 **对局结束！**<br>结果: `{result}` - {reason}")
            QMessageBox.information(self, "对局结束", f"结果: {result}\n原因: {reason}")

    def on_new_game(self):
        reply = QMessageBox.question(
            self, "新对局", "确定要重新开始一局新的对局吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.board_state.reset()
            self.chess_board.last_move = None
            self.chess_board.selected_square = None
            self.chess_board.legal_destinations.clear()
            self.chess_board.update()
            self.history_panel.clear()
            self.status_bar_label.setText("当前行动: 白方 (White)")
            self.status_bar_label.setStyleSheet("color: #f1faee; font-size: 15px; font-weight: bold;")

    def on_undo(self):
        """悔棋"""
        undone_move = self.board_state.undo_move()
        if undone_move:
            self.chess_board.last_move = self.board_state.board.peek() if len(self.board_state.board.move_stack) > 0 else None
            self.chess_board.selected_square = None
            self.chess_board.legal_destinations.clear()
            self.chess_board.update()
            self.history_panel.undo_last_move()
            
            turn_str = "白方 (White)" if self.board_state.turn == chess.WHITE else "黑方 (Black)"
            self.status_bar_label.setText(f"当前行动: {turn_str}")
        else:
            QMessageBox.warning(self, "提示", "当前已是初始局面，无法继续悔棋。")

    def on_flip(self):
        self.chess_board.flip_board()

    def on_export_pgn(self):
        """导出 PGN 棋谱文件或复制"""
        pgn_text = self.board_state.export_pgn()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出 PGN 棋谱", "game.pgn", "PGN Files (*.pgn);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(pgn_text)
                QMessageBox.information(self, "导出成功", f"PGN 棋谱已成功导出至:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出失败: {str(e)}")

    def on_export_fen(self):
        """导出 FEN 字符串并复制到剪贴板"""
        fen_str = self.board_state.get_fen()
        clipboard = QApplication.clipboard()
        clipboard.setText(fen_str)
        QMessageBox.information(
            self, "导出 FEN 成功",
            f"当前局面的 FEN 码已成功复制到系统剪贴板！\n\nFEN: {fen_str}"
        )

    def on_user_chat_message(self, message: str):
        """响应用户向女仆提问"""
        cfg = self.chat_panel.teaching_config
        if not cfg.master_enabled:
            self.chat_panel.append_maid_message("*(当前教学总开关已关闭，女仆处于静音状态。)*")
            return

        fen = self.board_state.get_fen()
        current_turn = "白方" if self.board_state.turn == chess.WHITE else "黑方"
        legal_count = len(list(self.board_state.board.legal_moves))
        
        reply = (
            f"主人，我已经收到您的提问：*“{message}”*。<br>"
            f"【当前局面】: 轮到 **{current_turn}** 行动，共有 **{legal_count}** 种合法走法。<br>"
            f"FEN: `{fen}`"
        )
        self.chat_panel.append_maid_message(reply)
