"""
主窗口 (模块1 - GUI 装配层)
负责协调 UI 布局（左侧:记谱表，中央:棋盘，右侧:LLM 对话窗口）
处理用户点击（新对局、悔棋、翻转、认输、求和、导出），与 GameController 进行全双工信号对接
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QMessageBox, QFileDialog, QApplication
)
import chess

from ..agents.base import ChessAgent
from ..agents.echo_agent import EchoAgent
from ..config import DEFAULT_MAID_PERSONA
from ..controller.game_controller import GameController
from .chess_board import ChessBoardWidget
from .move_history_panel import MoveHistoryPanel
from .chat_panel import ChatPanel
from .control_bar import ControlBar


class MainWindow(QMainWindow):
    def __init__(self, agent: ChessAgent = None, controller: GameController = None):
        super().__init__()
        self.setWindowTitle("ChessMaidBot - 国际象棋 AI 女仆教学对弈系统")
        self.resize(1320, 810)
        self.setStyleSheet("background-color: #14141a;")

        self.controller = controller or GameController()
        self.agent = agent or EchoAgent(persona_prompt=DEFAULT_MAID_PERSONA)

        # 注册 LLM 终局总结回调
        self.controller.set_llm_summary_provider(self._generate_llm_summary)

        self.init_ui()
        self.connect_controller()
        self.controller.new_game()

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
        self.control_bar.resign_requested.connect(self.on_resign)
        self.control_bar.draw_requested.connect(self.on_draw)
        self.control_bar.export_pgn_requested.connect(self.on_export_pgn)
        self.control_bar.export_fen_requested.connect(self.on_export_fen)
        self.control_bar.mode_changed.connect(self.controller.set_mode_label)
        self.control_bar.elo_changed.connect(self.controller.set_engine_elo)
        main_layout.addWidget(self.control_bar)

        # 2. 中间核心区：左侧记谱表 + 中央棋盘 + 右侧LLM对话 (三栏经典现代布局)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # [左侧]：走法历史双栏记谱表
        history_container = QVBoxLayout()
        history_title = QLabel("📜 对局记谱 (Move List)")
        history_title.setStyleSheet("color: #bbb; font-weight: bold; font-size: 13px;")
        history_container.addWidget(history_title)

        self.history_panel = MoveHistoryPanel(self)
        self.history_panel.setFixedWidth(240)
        history_container.addWidget(self.history_panel)
        content_layout.addLayout(history_container)

        # [中央]：棋盘区域 + 行动与将军状态指示
        board_container = QVBoxLayout()
        self.status_bar_label = QLabel("当前行动: 白方 (White)")
        self.status_bar_label.setStyleSheet("color: #f1faee; font-size: 15px; font-weight: bold; padding: 4px;")
        board_container.addWidget(self.status_bar_label)

        self.chess_board = ChessBoardWidget(self.controller.board_state, self)
        self.chess_board.move_ready.connect(self.controller.apply_move)
        board_container.addWidget(self.chess_board)
        content_layout.addLayout(board_container)

        # [右侧]：LLM 女仆互动对话窗口
        self.chat_panel = ChatPanel(self.controller.teaching, self)
        self.chat_panel.message_sent.connect(self.on_user_chat_message)
        self.chat_panel.teaching_triggers_changed.connect(self.controller.set_teaching)
        content_layout.addWidget(self.chat_panel)

        main_layout.addLayout(content_layout)

    def connect_controller(self):
        ctrl = self.controller
        ctrl.position_changed.connect(self.chess_board.show_move)
        ctrl.history_changed.connect(self.history_panel.set_records)
        ctrl.status_changed.connect(self.on_status_changed)
        ctrl.move_played.connect(self.on_move_played)
        ctrl.game_over.connect(self.on_game_over)
        ctrl.game_reset.connect(self.on_game_reset)
        ctrl.engine_thinking_changed.connect(self.on_engine_thinking)

    def _generate_llm_summary(self, snapshot) -> str:
        """为终局持久化生成高质量的 LLM 总结"""
        req = self.controller.build_agent_request(
            user_message="请对本局对弈进行全面的复盘总结，点评双方亮点与失误。",
            persona_prompt=DEFAULT_MAID_PERSONA,
        )
        return self.agent.reply(req)

    # ---------- 调度层信号处理 ----------

    def on_status_changed(self, text: str, in_check: bool):
        self.status_bar_label.setText(text)
        color = "#ff5252" if in_check else "#f1faee"
        self.status_bar_label.setStyleSheet(
            f"color: {color}; font-size: 15px; font-weight: bold; padding: 4px;"
        )

    def on_engine_thinking(self, thinking: bool):
        if thinking:
            self.status_bar_label.setText("🤖 Stockfish 思考中 (Thinking)...")
            self.status_bar_label.setStyleSheet("color: #ffa726; font-size: 15px; font-weight: bold; padding: 4px;")
            self.chess_board.setEnabled(False)
        else:
            self.chess_board.setEnabled(True)

    def on_move_played(self, san: str, uci: str, was_white: bool):
        """教学触发: 当下局面评估 (将军提醒)"""
        triggers = self.controller.teaching
        if triggers.master_enabled and triggers.eval_current_position and self.controller.board_state.is_check():
            side_cn = "白方" if was_white else "黑方"
            self.chat_panel.append_maid_message(
                f"主人，**{side_cn}** 走出了 **`{san}`** 并发动了将军！请仔细应对防守哦。"
            )

    def on_game_over(self, status: dict):
        reason = status.get("reason", "对局结束")
        result = status.get("result", "")
        triggers = self.controller.teaching
        if triggers.master_enabled and triggers.game_over_summary:
            self.chat_panel.append_maid_message(f"🏁 **对局结束！**<br>结果: `{result}` - {reason}")
        QMessageBox.information(self, "对局结束", f"结果: {result}\n原因: {reason}")

    def on_game_reset(self):
        self.chess_board.reset_view()

    # ---------- 控制栏动作 ----------

    def on_new_game(self):
        reply = QMessageBox.question(
            self, "新对局", "确定要重新开始一局新的对局吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.controller.new_game()

    def on_undo(self):
        if not self.controller.undo():
            QMessageBox.warning(self, "提示", "当前已是初始局面，无法继续悔棋。")

    def on_flip(self):
        self.chess_board.flip_board()

    def on_resign(self):
        """认输操作"""
        turn_cn = "白方" if self.controller.board_state.turn == chess.WHITE else "黑方"
        reply = QMessageBox.question(
            self, "确认认输", f"确定要让当前行动方（{turn_cn}）认输吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.controller.resign(is_white=(self.controller.board_state.turn == chess.WHITE))

    def on_draw(self):
        """求和操作"""
        res = self.controller.offer_draw()
        if res.get("accepted") and res.get("requires_confirm"):
            # 本地双人对弈，需要对方确认
            reply = QMessageBox.question(
                self, "提议和棋", "对方发起了和棋请求，请问是否同意和棋？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.controller.accept_draw()
        elif not res.get("accepted"):
            QMessageBox.information(self, "求和结果", res.get("reason", "求和未成功。"))

    def on_export_pgn(self):
        """导出 PGN 棋谱文件"""
        pgn_text = self.controller.export_pgn()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出 PGN 棋谱", "game.pgn", "PGN Files (*.pgn);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(pgn_text)
                QMessageBox.information(self, "导出成功", f"PGN 棋谱已成功导出至:\n{file_path}")
            except OSError as e:
                QMessageBox.critical(self, "导出失败", f"导出失败: {str(e)}")

    def on_export_fen(self):
        """导出 FEN 字符串并复制到剪贴板"""
        fen_str = self.controller.get_fen()
        QApplication.clipboard().setText(fen_str)
        QMessageBox.information(
            self, "导出 FEN 成功",
            f"当前局面的 FEN 码已成功复制到系统剪贴板！\n\nFEN: {fen_str}"
        )

    # ---------- LLM 对话链路 ----------

    def on_user_chat_message(self, message: str):
        if not self.controller.teaching.master_enabled:
            self.chat_panel.append_maid_message("*(当前教学总开关已关闭，女仆处于静音状态。)*")
            return

        request = self.controller.build_agent_request(message, persona_prompt=DEFAULT_MAID_PERSONA)
        reply = self.agent.reply(request)
        self.chat_panel.append_maid_message(reply)

