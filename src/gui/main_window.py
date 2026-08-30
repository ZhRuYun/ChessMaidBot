"""
主窗口 (模块1 - GUI 装配层)
负责协调 UI 布局（左侧:记谱表，中央:棋盘，右侧:LLM 对话窗口）
处理用户交互（新对局、悔棋、翻转、认输、求和、一键导出 PGN+FEN、主动询问LLM、落子自动触发教学）
"""
from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QFrame,
    QLabel, QPushButton, QMessageBox, QApplication, QInputDialog
)
from PySide6.QtCore import QThread, Signal, Qt, QEvent
import chess

from ..agents.base import ChessAgent, AgentRequest
from ..agents.llm_agent import LLMAgent
from ..agents.prompt_builder import PromptBuilder
from ..config import DEFAULT_MAID_PERSONA, CONFIG_FILE_PATH
from ..controller.game_controller import GameController
from ..controller.game_modes import GameMode
from ..controller.online_match import EmbeddedOnlineServer, OnlineMatchClient
from .chess_board import ChessBoardWidget
from .move_history_panel import MoveHistoryPanel
from .chat_panel import ChatPanel
from .control_bar import ControlBar
import json


class LLMWorker(QThread):
    """异步执行 LLM 请求的后台线程，配合 UI 显示 loading spinner"""
    response_ready = Signal(str)
    failed = Signal(str)

    def __init__(self, agent: ChessAgent, request: AgentRequest, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.request = request

    def run(self):
        try:
            reply = self.agent.reply(self.request)
            self.response_ready.emit(reply)
        except Exception as e:
            self.failed.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self, agent: ChessAgent = None, controller: GameController = None):
        super().__init__()
        self.setWindowTitle("ChessMaidBot - 国际象棋 AI 女仆教学对弈系统")
        self.resize(1340, 820)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b0f19;
            }
            QWidget {
                color: #f1f5f9;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }
            QMessageBox {
                background-color: #1e222d;
                color: #f1f5f9;
            }
            QMessageBox QPushButton {
                background-color: #334155;
                color: #ffffff;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 5px 12px;
            }
            QMessageBox QPushButton:hover {
                background-color: #475569;
            }
        """)

        self.controller = controller or GameController()
        # 加载持久化配置
        self._persisted_config = self._load_persisted_settings()
        # 当前生效的人设 Prompt (可被用户通过「人设」按钮运行时修改)
        self.current_persona = self._persisted_config.get("persona") or DEFAULT_MAID_PERSONA
        # 默认使用 LLMAgent (优先使用持久化配置)
        llm_cfg = self._persisted_config.get("llm", {})
        self.controller.search_api_url = llm_cfg.get("search_api_url", "")
        self.controller.search_api_key = llm_cfg.get("search_api_key", "")
        self.agent = agent or LLMAgent(
            api_base=llm_cfg.get("api_base") or None,
            api_key=llm_cfg.get("api_key") or None,
            model=llm_cfg.get("model") or None,
            reasoning_effort=llm_cfg.get("reasoning_effort") or None,
            stream=llm_cfg.get("stream", False),
            persona_prompt=self.current_persona,
        )
        if isinstance(self.agent, LLMAgent) and "show_tool_records" in llm_cfg:
            self.agent.show_tool_records = bool(llm_cfg["show_tool_records"])

        self.controller.set_agent(self.agent)
        self._llm_thread: Optional[LLMWorker] = None
        self._online_server: Optional[EmbeddedOnlineServer] = None
        self._online_client: Optional[OnlineMatchClient] = None

        # 注册 LLM 终局总结回调
        self.controller.set_llm_summary_provider(self._generate_llm_summary)

        self.init_ui()
        self.connect_controller()
        # 初始化 chat_panel 连接状态徽章 (反映 LLMAgent 当前是否配置了 Key)
        self._sync_llm_connection_status()
        self.controller.new_game()

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 9, 16, 14)
        main_layout.setSpacing(8)

        # 1. 固定高度的顶部区域：控制栏与横线到窗口顶部的距离不受其他布局影响。
        top_region = QWidget(self)
        top_region.setFixedHeight(54)
        top_layout = QVBoxLayout(top_region)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(2)

        self.control_bar = ControlBar(top_region)
        self.control_bar.new_game_requested.connect(self.on_new_game)
        self.control_bar.undo_requested.connect(self.on_undo)
        self.control_bar.flip_requested.connect(self.on_flip)
        self.control_bar.resign_requested.connect(self.on_resign)
        self.control_bar.draw_requested.connect(self.on_draw)
        self.control_bar.import_state_requested.connect(self.on_import_game_state)
        self.control_bar.export_state_requested.connect(self.on_export_game_state)
        self.control_bar.llm_config_requested.connect(self.on_open_llm_config)
        self.control_bar.mode_changed.connect(self.controller.set_mode_label)
        self.control_bar.elo_changed.connect(self.controller.set_engine_elo)
        self.control_bar.theme_changed.connect(self.on_theme_changed)
        top_layout.addWidget(self.control_bar, stretch=1)

        # 固定横向边界：约束顶部控制栏与三栏工作区，不参与拖拽。
        self.toolbar_boundary = QFrame(top_region)
        self.toolbar_boundary.setObjectName("toolbarBoundary")
        self.toolbar_boundary.setFixedHeight(2)
        self.toolbar_boundary.setFrameShape(QFrame.HLine)
        self.toolbar_boundary.setStyleSheet("background-color: #334155; border: none;")
        top_layout.addWidget(self.toolbar_boundary)
        main_layout.addWidget(top_region)

        # 2. 中间核心区：使用 QSplitter 提供两条可拖拽竖向分隔线。
        self.content_splitter = QSplitter(Qt.Horizontal, self)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.setHandleWidth(5)
        self.content_splitter.setStyleSheet("""
            QSplitter::handle:horizontal {
                background-color: #334155;
                margin: 4px 1px;
                border-radius: 2px;
            }
            QSplitter::handle:horizontal:hover,
            QSplitter::handle:horizontal:pressed {
                background-color: #38bdf8;
            }
        """)

        # [左侧]：走法历史双栏记谱表
        history_widget = QWidget(self.content_splitter)
        history_container = QVBoxLayout(history_widget)
        history_container.setContentsMargins(0, 0, 0, 0)
        history_title = QLabel("走法记谱 (Moves)")
        history_title.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 13px; padding-bottom: 2px;")
        history_container.addWidget(history_title)

        self.history_panel = MoveHistoryPanel(history_widget)
        history_widget.setMinimumWidth(190)
        self.history_panel.nav_first_requested.connect(self.on_nav_first)
        self.history_panel.nav_prev_requested.connect(self.on_nav_prev)
        self.history_panel.nav_next_requested.connect(self.on_nav_next)
        self.history_panel.nav_last_requested.connect(self.on_nav_last)
        self.history_panel.move_selected.connect(self.on_history_move_selected)
        history_container.addWidget(self.history_panel)
        self.content_splitter.addWidget(history_widget)

        # [中央]：棋盘区域 + 行动与将军状态指示
        self.board_workspace = QWidget(self.content_splitter)
        self.board_container = QVBoxLayout(self.board_workspace)
        self.board_container.setContentsMargins(8, 0, 8, 0)
        self.board_container.setSpacing(8)
        self.status_bar_label = QLabel("当前行动: 白方 (White)")
        self.status_bar_label.setAlignment(Qt.AlignCenter)
        self.status_bar_label.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: 700; padding: 4px;")
        self.board_container.addWidget(self.status_bar_label)

        self.chess_board = ChessBoardWidget(self.controller.board_state, self.board_workspace)
        self.chess_board.move_ready.connect(self.controller.apply_move)

        # 棋盘与右侧竖排动作按钮同处一行，顶端对齐。
        self.board_row_widget = QWidget(self.board_workspace)
        board_row = QHBoxLayout(self.board_row_widget)
        board_row.setContentsMargins(0, 0, 0, 0)
        board_row.setSpacing(8)
        board_row.addWidget(self.chess_board, alignment=Qt.AlignTop)

        action_widget = QWidget(self.board_row_widget)
        action_column = QVBoxLayout(action_widget)
        action_column.setContentsMargins(0, 0, 0, 0)
        action_column.setSpacing(8)
        for text, handler, destructive in (
            ("悔棋", self.on_undo, False),
            ("求和", self.on_draw, False),
            ("认输", self.on_resign, True),
        ):
            button = QPushButton(text, action_widget)
            button.setFixedWidth(62)
            if destructive:
                button.setStyleSheet("QPushButton { background-color: #31181e; color: #fca5a5; border: 1px solid #5c242e; border-radius: 6px; padding: 6px 10px; } QPushButton:hover { background-color: #451d27; color: white; border-color: #ef4444; }")
            else:
                button.setStyleSheet("QPushButton { background-color: #1e222d; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; padding: 6px 10px; } QPushButton:hover { background-color: #282f3e; color: white; border-color: #60a5fa; }")
            button.clicked.connect(handler)
            action_column.addWidget(button)
        board_row.addWidget(action_widget, alignment=Qt.AlignTop)
        self.board_container.addWidget(self.board_row_widget, alignment=Qt.AlignTop | Qt.AlignHCenter)

        # 走法导航按钮位于棋盘正下方，宽度与棋盘同步。
        self.nav_widget = QWidget(self.board_workspace)
        nav_layout = QHBoxLayout(self.nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)
        nav_style = "QPushButton { background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px; font-weight: bold; padding: 4px 18px; } QPushButton:hover { border-color: #38bdf8; color: white; }"
        for text, handler in (("|<", self.on_nav_first), ("<", self.on_nav_prev), (">", self.on_nav_next), (">|", self.on_nav_last)):
            button = QPushButton(text, self.nav_widget)
            button.setFixedHeight(28)
            button.setStyleSheet(nav_style)
            button.clicked.connect(handler)
            nav_layout.addWidget(button)
        self.nav_widget.setFixedWidth(self.chess_board.width())
        self.board_container.addWidget(self.nav_widget, alignment=Qt.AlignTop | Qt.AlignHCenter)

        self.board_workspace.setMinimumWidth(ChessBoardWidget.MIN_SQUARE_SIZE * 8 + 90)
        self.content_splitter.addWidget(self.board_workspace)
        # 中央区域尺寸变化时自适应缩放棋盘。
        self.board_workspace.installEventFilter(self)

        # [右侧]：LLM 女仆互动对话窗口
        self.chat_panel = ChatPanel(self.controller.teaching, self.content_splitter)
        self.chat_panel.setMinimumWidth(260)
        self.chat_panel.message_sent.connect(self.on_user_chat_message)
        self.chat_panel.ask_llm_requested.connect(self.on_ask_llm_requested)
        self.chat_panel.teaching_triggers_changed.connect(self.controller.set_teaching)
        self.content_splitter.addWidget(self.chat_panel)

        # 默认比例接近原布局；之后可拖动任一竖线自由调整相邻区域宽度。
        self.content_splitter.setStretchFactor(0, 0)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setStretchFactor(2, 1)
        self.content_splitter.setSizes([240, 560, 440])
        main_layout.addWidget(self.content_splitter, stretch=1)

    def eventFilter(self, obj, event):
        """中央区域尺寸变化时，按可用空间自适应缩放棋盘。"""
        if obj is self.board_workspace and event.type() == QEvent.Resize:
            self._adjust_board_size()
        return super().eventFilter(obj, event)

    def _adjust_board_size(self):
        """棋盘随中间区域扩大而适当变大，但绝不超出上下可用边界。"""
        spacing = self.board_container.spacing() or 0
        margins = self.board_container.contentsMargins()
        reserved_height = (
            self.status_bar_label.sizeHint().height()
            + self.nav_widget.sizeHint().height()
            + spacing * 2
        )
        available_height = self.board_workspace.height() - reserved_height
        available_width = (
            self.board_workspace.width()
            - margins.left() - margins.right()
            - 62 - 8  # 右侧动作按钮列宽及其与棋盘的间距
        )
        self.chess_board.set_board_pixel_size(
            max(min(available_width, available_height), 0)
        )
        self.nav_widget.setFixedWidth(self.chess_board.width())

    def connect_controller(self):
        ctrl = self.controller
        ctrl.position_changed.connect(self.chess_board.show_move)
        ctrl.history_changed.connect(self.history_panel.set_records)
        ctrl.status_changed.connect(self.on_status_changed)
        ctrl.move_played.connect(self.on_move_played)
        ctrl.game_over.connect(self.on_game_over)
        ctrl.game_reset.connect(self.on_game_reset)
        ctrl.engine_thinking_changed.connect(self.on_engine_thinking)
        ctrl.engine_error.connect(self.on_engine_error)

    def _generate_llm_summary(self, snapshot) -> str:
        """为终局持久化生成高质量的 LLM 总结"""
        custom_prompt = PromptBuilder.build_custom_prompt(
            snapshot=snapshot,
            triggers=self.controller.teaching,
            is_auto_move=False,
            extra_note="本局已终局，请为对局归档提供精准全面的技术复盘总结。",
        )
        req = self.controller.build_agent_request(
            user_message=custom_prompt,
            persona_prompt=self.current_persona,
        )
        return self.agent.reply(req)

    # ---------- 调度层信号处理 ----------

    def on_status_changed(self, text: str, in_check: bool):
        self.status_bar_label.setText(text)
        color = "#ef4444" if in_check else "#38bdf8"
        self.status_bar_label.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: 700; padding: 4px;"
        )

    def on_engine_thinking(self, thinking: bool):
        if thinking:
            self.status_bar_label.setText("Stockfish / AI 思考中...")
            self.status_bar_label.setStyleSheet("color: #fbbf24; font-size: 14px; font-weight: 700; padding: 4px;")
            self.chess_board.setEnabled(False)
        else:
            self.chess_board.setEnabled(True)

    def on_engine_error(self, error_msg: str):
        """显示引擎故障，避免人机模式无响应却没有任何反馈。"""
        self.status_bar_label.setText("Stockfish 无法走棋")
        self.status_bar_label.setStyleSheet("color: #ef4444; font-size: 14px; font-weight: 700; padding: 4px;")
        QMessageBox.warning(
            self,
            "Stockfish 引擎错误",
            f"Stockfish 无法完成走棋：\n\n{error_msg}\n\n"
            "请确认 engines/stockfish.exe 存在且能够正常运行。",
        )

    def on_move_played(self, san: str, uci: str, was_white: bool):
        """
        要求2：若总开关开启，玩家每走一步棋，根据棋盘现状信息 (PGN, FEN) 和 4 个子开关启动情况，
        向 LLM 发送定制 prompt 并等待回复 (异步 + loading 转圈动效)
        """
        if self._online_client and self.controller.modes.mode == GameMode.ONLINE_PVP:
            # 判断这步是否是自己走的，如果是则同步发送给服务端
            is_my_move = (was_white and self._online_client.my_side == "white") or (not was_white and self._online_client.my_side == "black")
            if is_my_move:
                self._online_client.send_move(uci, self.controller.get_fen())

        triggers = self.controller.teaching
        if not triggers.master_enabled or not self._has_configured_llm_api():
            return

        # 构建内部教学 prompt。它只发送给模型，不写入聊天展示区。
        snapshot = self.controller.get_snapshot()
        custom_prompt = PromptBuilder.build_custom_prompt(
            snapshot=snapshot,
            triggers=triggers,
            is_auto_move=True,
            game_mode_name=self.controller.modes.mode.value,
        )
        self._dispatch_llm_request(custom_prompt)

    def on_game_over(self, status: dict):
        result = status.get("result", "*")
        reason = status.get("reason", "")
        self.chat_panel.append_maid_message(f"**对局结束！**<br>结果: `{result}` - {reason}")
        QMessageBox.information(self, "对局结束", f"结果: {result}\n原因: {reason}")

    def on_game_reset(self):
        self.chess_board.reset_view()

    # ---------- 走法导航动作 (Lichess 风格) ----------

    def _get_history_boards_and_moves(self):
        """重演走法栈生成每一步的 (Board, Move) 序列"""
        boards = []
        moves = []
        replay = self.controller.board_state.board.copy()
        while replay.move_stack:
            replay.pop()
        
        boards.append(replay.copy())
        moves.append(None)

        for move in self.controller.board_state.board.move_stack:
            replay.push(move)
            boards.append(replay.copy())
            moves.append(move)
        return boards, moves

    def _get_current_preview_index(self, boards) -> int:
        if self.chess_board.preview_board is None:
            return len(boards) - 1
        cur_fen = self.chess_board.preview_board.fen()
        for idx, b in enumerate(boards):
            if b.fen() == cur_fen:
                return idx
        return len(boards) - 1

    def on_nav_first(self):
        boards, moves = self._get_history_boards_and_moves()
        if boards:
            self.chess_board.set_preview_board(boards[0], moves[0])

    def on_nav_last(self):
        self.chess_board.set_preview_board(None, self.controller.board_state.last_move)

    def on_nav_prev(self):
        boards, moves = self._get_history_boards_and_moves()
        if not boards:
            return
        idx = self._get_current_preview_index(boards)
        if idx > 0:
            self.chess_board.set_preview_board(boards[idx - 1], moves[idx - 1])

    def on_nav_next(self):
        boards, moves = self._get_history_boards_and_moves()
        if not boards:
            return
        idx = self._get_current_preview_index(boards)
        if idx < len(boards) - 1:
            if idx + 1 == len(boards) - 1:
                self.on_nav_last()
            else:
                self.chess_board.set_preview_board(boards[idx + 1], moves[idx + 1])

    def on_history_move_selected(self, row: int, col: int):
        boards, moves = self._get_history_boards_and_moves()
        # row: 0-indexed; col: 1 for white, 2 for black
        step_idx = row * 2 + (1 if col == 1 else 2)
        if 0 <= step_idx < len(boards):
            if step_idx == len(boards) - 1:
                self.on_nav_last()
            else:
                self.chess_board.set_preview_board(boards[step_idx], moves[step_idx])

    # ---------- 控制栏动作 ----------

    def on_new_game(self):
        reply = QMessageBox.question(
            self, "新对局", "确定要重新开始一局新的对局吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # 如果是人机或女仆对弈模式，弹出选择执白还是执黑
        if self.controller.modes.mode in (GameMode.VS_ENGINE, GameMode.VS_MAID_LLM):
            side_dialog = QMessageBox(self)
            side_dialog.setWindowTitle("选择执棋方")
            side_dialog.setText("请选择您在本局中执白棋还是执黑棋：")
            btn_white = side_dialog.addButton("执白 (先手)", QMessageBox.ActionRole)
            btn_black = side_dialog.addButton("执黑 (后手)", QMessageBox.ActionRole)
            side_dialog.exec()
            chosen_side = "black" if side_dialog.clickedButton() == btn_black else "white"
            self.controller.set_player_side(chosen_side)
            if chosen_side == "black" and not self.chess_board.is_flipped:
                self.chess_board.flip_board()
            elif chosen_side == "white" and self.chess_board.is_flipped:
                self.chess_board.flip_board()

        elif self.controller.modes.mode == GameMode.ONLINE_PVP:
            self._handle_online_pvp_setup()

        self.controller.new_game()

    def _handle_online_pvp_setup(self):
        """网络双人对战连接设置对话框"""
        from .online_match_dialog import OnlineMatchDialog
        config = OnlineMatchDialog.get_online_config(self)
        if not config:
            return

        is_host = config["is_host"]
        host = config["host"]
        port = config["port"]
        my_side = config["my_side"]

        if is_host:
            if self._online_server is not None:
                self._online_server.stop()
            self._online_server = EmbeddedOnlineServer(host="0.0.0.0", port=port)
            self._online_server.start()

            if self._online_client is not None:
                self._online_client.stop()
            self._online_client = OnlineMatchClient(host="127.0.0.1", port=port, parent=self)
            self._online_client.opponent_moved.connect(self._on_online_opponent_move)
            self._online_client.start(my_side=my_side)
            self.controller.set_player_side(my_side)
            if my_side == "black" and not self.chess_board.is_flipped:
                self.chess_board.flip_board()
            elif my_side == "white" and self.chess_board.is_flipped:
                self.chess_board.flip_board()
            QMessageBox.information(self, "房间已建立", f"已成功启动本地对战服务 (端口 {port})！您执{'白方' if my_side=='white' else '黑方'}，请通知对手连接。")
        else:
            if self._online_client is not None:
                self._online_client.stop()
            self._online_client = OnlineMatchClient(host=host, port=port, parent=self)
            self._online_client.opponent_moved.connect(self._on_online_opponent_move)
            self._online_client.start(my_side=my_side)
            self.controller.set_player_side(my_side)
            if my_side == "black" and not self.chess_board.is_flipped:
                self.chess_board.flip_board()
            elif my_side == "white" and self.chess_board.is_flipped:
                self.chess_board.flip_board()
            QMessageBox.information(self, "已连接", f"已连接至房间 {host}:{port}！您执{'白方' if my_side=='white' else '黑方'}。")

    def _on_online_opponent_move(self, uci_move: str):
        try:
            move = chess.Move.from_uci(uci_move)
            self.controller.apply_move(move)
        except Exception:
            pass

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

    def on_import_game_state(self):
        """根据 PGN/FEN 导入棋局"""
        text, ok = QInputDialog.getMultiLineText(
            self, "导入棋局 (PGN / FEN)", "请粘贴完整的 PGN 文本或 FEN 字符串:"
        )
        if ok and text.strip():
            success = self.controller.import_game(text.strip())
            if success:
                self.chess_board.reset_view()
                QMessageBox.information(self, "导入成功", "棋局已成功加载！")
            else:
                QMessageBox.warning(self, "导入失败", "未能解析给定的 PGN 或 FEN 文本，请检查格式是否正确。")

    def on_export_game_state(self):
        """
        要求6：一键将 PGN + FEN 码导出到系统剪贴板中
        """
        pgn_text = self.controller.export_pgn().strip()
        fen_str = self.controller.get_fen().strip()

        combined_export = f"""=== PGN ===\n{pgn_text}\n\n=== FEN ===\n{fen_str}"""

        QApplication.clipboard().setText(combined_export)
        QMessageBox.information(
            self,
            "导出棋局状态成功",
            "已一键将【PGN + FEN】完整棋局状态复制到系统剪切板！\n可直接粘贴使用。"
        )

    # ---------- 主题变换 ----------

    def on_theme_changed(self, theme_name: str):
        is_light = (theme_name == "浅色")
        if hasattr(self, "chat_panel"):
            self.chat_panel.apply_theme(is_light)
        if hasattr(self, "control_bar"):
            self.control_bar.apply_theme(is_light)
        if hasattr(self, "move_history"):
            self.move_history.apply_theme(is_light)

        if theme_name == "浅色":
            self.setStyleSheet("""
                QMainWindow { background-color: #f8fafc; }
                QWidget { color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
                QMessageBox { background-color: #ffffff; color: #0f172a; }
                QMessageBox QPushButton { background-color: #e2e8f0; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 5px 12px; }
                QTableWidget { background-color: #ffffff; color: #0f172a; gridline-color: #e2e8f0; border: 1px solid #cbd5e1; }
                QHeaderView::section { background-color: #f1f5f9; color: #475569; border-bottom: 1px solid #cbd5e1; }
                QTextBrowser { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }
                QLineEdit { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }
                QComboBox { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }
                QSpinBox { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }
                QPushButton { background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; }
            """)
        elif theme_name == "深色":
            self.setStyleSheet("""
                QMainWindow { background-color: #0b0f19; }
                QWidget { color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
                QMessageBox { background-color: #1e222d; color: #f1f5f9; }
                QMessageBox QPushButton { background-color: #334155; color: #ffffff; border: 1px solid #475569; border-radius: 4px; padding: 5px 12px; }
                QTableWidget { background-color: #0f172a; color: #e2e8f0; gridline-color: #1e293b; border: 1px solid #1e293b; }
                QHeaderView::section { background-color: #1e293b; color: #94a3b8; border-bottom: 1px solid #334155; }
                QTextBrowser { background-color: #0b0f19; color: #e2e8f0; border: 1px solid #1e293b; }
                QLineEdit { background-color: #111827; color: #f8fafc; border: 1px solid #334155; }
            """)
        else: # 跟随系统
            self.setStyleSheet("""
                QMainWindow { background-color: #0b0f19; }
                QWidget { color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
                QMessageBox { background-color: #1e222d; color: #f1f5f9; }
                QMessageBox QPushButton { background-color: #334155; color: #ffffff; border: 1px solid #475569; border-radius: 4px; padding: 5px 12px; }
                QTableWidget { background-color: #0f172a; color: #e2e8f0; gridline-color: #1e293b; border: 1px solid #1e293b; }
                QHeaderView::section { background-color: #1e293b; color: #94a3b8; border-bottom: 1px solid #334155; }
                QTextBrowser { background-color: #0b0f19; color: #e2e8f0; border: 1px solid #1e293b; }
                QLineEdit { background-color: #111827; color: #f8fafc; border: 1px solid #334155; }
            """)

    # ---------- AI 女仆连接配置 ----------

    def on_open_llm_config(self):
        """打开综合 AI 配置对话框"""
        current_config = self._collect_current_llm_config()
        from .llm_config_dialog import LLMConfigDialog
        res = LLMConfigDialog.get_config_dialog(
            current_config=current_config,
            current_triggers=self.controller.teaching,
            current_persona=self.current_persona,
            parent=self,
        )
        if res is None:
            return  # 用户取消

        new_config = res.get("config", {})
        new_triggers = res.get("triggers")
        new_persona = res.get("persona")

        if new_triggers:
            self.controller.set_teaching(new_triggers)
        if new_persona:
            self.current_persona = new_persona

        # 重建 LLMAgent
        self.agent = LLMAgent(
            api_base=new_config.get("api_base") or None,
            api_key=new_config.get("api_key") or None,
            model=new_config.get("model") or None,
            reasoning_effort=new_config.get("reasoning_effort") or None,
            stream=new_config.get("stream", False),
            persona_prompt=self.current_persona,
        )
        if "show_tool_records" in new_config:
            self.agent.show_tool_records = bool(new_config["show_tool_records"])

        self.controller.search_api_url = new_config.get("search_api_url", "")
        self.controller.search_api_key = new_config.get("search_api_key", "")
        self._persisted_search_api_url = self.controller.search_api_url
        self._persisted_search_api_key = self.controller.search_api_key

        self.controller.set_agent(self.agent)
        self._sync_llm_connection_status()
        self._save_persisted_settings()

        QMessageBox.information(
            self, "AI 设置已保存",
            "已成功更新 AI 连接配置、联网搜索接口、教学触发器与人设！"
        )

    def _collect_current_llm_config(self) -> dict:
        """从当前 agent 收集配置, 用于预填配置对话框"""
        if isinstance(self.agent, LLMAgent):
            return {
                "api_base": self.agent.api_base,
                "api_key": self.agent.api_key,
                "model": self.agent.model,
                "search_api_url": getattr(self.controller, "search_api_url", ""),
                "search_api_key": getattr(self.controller, "search_api_key", ""),
                "reasoning_effort": self.agent.reasoning_effort,
                "stream": self.agent.stream,
                "show_tool_records": getattr(self.agent, "show_tool_records", False),
            }
        return {
            "search_api_url": getattr(self.controller, "search_api_url", ""),
            "search_api_key": getattr(self.controller, "search_api_key", ""),
        }

    def _load_persisted_settings(self) -> dict:
        """从 data/settings.json 加载持久化设置"""
        if CONFIG_FILE_PATH.exists():
            try:
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_persisted_settings(self):
        """保存持久化设置到 data/settings.json"""
        data = {
            "persona": self.current_persona,
            "llm": self._collect_current_llm_config(),
        }
        try:
            CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _has_configured_llm_api(self) -> bool:
        """自动教学仅在真实 LLM Agent 已配置 API Key 时启用。"""
        return isinstance(self.agent, LLMAgent) and bool(self.agent.api_key.strip())

    def _sync_llm_connection_status(self):
        """根据当前 agent 的 Key 配置, 同步 chat_panel 状态徽章"""
        if isinstance(self.agent, LLMAgent):
            connected = self._has_configured_llm_api()
            self.chat_panel.set_llm_connected(connected, self.agent.model)
        else:
            # 非 LLMAgent (如测试用 EchoAgent) 默认显示在线
            self.chat_panel.set_llm_connected(True, "")

    # ---------- 人设 Prompt 自定义 ----------

    def on_open_persona_config(self):
        """打开人设 Prompt 自定义对话框, 应用后更新 current_persona 与 agent"""
        from .persona_config_dialog import PersonaConfigDialog
        new_persona = PersonaConfigDialog.get_persona_dialog(
            current_persona=self.current_persona, parent=self
        )
        if new_persona is None:
            return  # 用户取消

        # 更新当前人设状态 (后续所有 build_agent_request 调用都会使用它)
        self.current_persona = new_persona

        # 同步更新 agent 实例的人设
        if isinstance(self.agent, LLMAgent):
            self.agent.set_persona(new_persona)
        elif hasattr(self.agent, "persona_prompt"):
            # 兼容其他类型的 Agent (如带 persona_prompt 属性的 EchoAgent)
            self.agent.persona_prompt = new_persona

        # 友好的反馈提示
        QMessageBox.information(
            self, "人设已更新",
            "AI 女仆的人设 Prompt 已成功更新！\n\n"
            "后续对话与教学将使用新人设。新对局也会沿用此人设。\n\n"
            f"当前人设 (前 30 字): {new_persona[:30]}..."
        )

    # ---------- LLM 对话链路 ----------

    def on_ask_llm_requested(self):
        """
        要求4：主动询问 LLM 按钮触发的定制 prompt
        """
        triggers = self.controller.teaching
        snapshot = self.controller.get_snapshot()
        custom_prompt = PromptBuilder.build_custom_prompt(
            snapshot=snapshot,
            triggers=triggers,
            is_auto_move=False,
            game_mode_name=self.controller.modes.mode.value,
        )
        self.chat_panel.append_user_message("*(点击了「主动询问女仆指导」)*")
        self._dispatch_llm_request(custom_prompt)

    def on_user_chat_message(self, message: str):
        """手动输入框发送消息"""
        self._dispatch_llm_request(message)

    def _dispatch_llm_request(self, message: str):
        """异步调度 LLM 请求，展示 Loading 旋转控件"""
        if self._llm_thread is not None and self._llm_thread.isRunning():
            self._llm_thread.terminate()
            self._llm_thread.wait(300)

        self.chat_panel.set_loading(True)
        request = self.controller.build_agent_request(message, persona_prompt=self.current_persona)

        self._llm_thread = LLMWorker(self.agent, request, parent=self)
        self._llm_thread.response_ready.connect(self._on_llm_response)
        self._llm_thread.failed.connect(self._on_llm_failed)
        self._llm_thread.start()

    def _on_llm_response(self, reply: str):
        self.chat_panel.set_loading(False)
        self.chat_panel.append_maid_message(reply)

    def _on_llm_failed(self, error_msg: str):
        self.chat_panel.set_loading(False)
        self.chat_panel.append_maid_message(f"*(女仆回复出现异常: {error_msg})*")
