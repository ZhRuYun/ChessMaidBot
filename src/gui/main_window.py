"""
主窗口 (模块1 - GUI 装配层)
负责协调 UI 布局（左侧:记谱表，中央:棋盘，右侧:LLM 对话窗口）
处理用户交互（新对局、悔棋、翻转、认输、求和、一键导出 PGN+FEN、主动询问LLM、落子自动触发教学）

LLM 工程化:
  - 自动教学/主动询问请求接入语义缓存 (同局面+同开关直接复用回复, 削减重复 Token)
  - 短期记忆只存「用户意图标签 + 女仆回复正文」, 不再存含完整 PGN 的提示词 (Token 瘦身)
  - 终局总结走两段式流水线 (教练结构化分析 -> 女仆人格化改写) 并回填长期画像
"""
import copy
import inspect
import logging
from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QFrame,
    QLabel, QMessageBox, QApplication, QInputDialog
)
from PySide6.QtCore import QThread, Signal, Qt
import chess
import json

from ..agents.base import ChessAgent, AgentRequest
from ..agents.llm_agent import LLMAgent
from ..agents.prompt_builder import PromptBuilder
from ..agents.semantic_cache import SemanticCache
from ..agents.memory import ShortTermMemory, LongTermMemory
from ..config import DEFAULT_MAID_PERSONA, CONFIG_FILE_PATH
from ..controller.game_controller import GameController
from ..controller.game_modes import GameMode
from ..controller.online_match import EmbeddedOnlineServer, OnlineMatchClient
from .chess_board import ChessBoardWidget
from .move_history_panel import MoveHistoryPanel
from .chat_panel import ChatPanel
from .control_bar import ControlBar

logger = logging.getLogger("chessmaid.gui")


class LLMWorker(QThread):
    """异步执行 LLM 请求的后台线程，支持流式逐字输出与取消控制"""
    chunk_ready = Signal(str, int)     # (流式片段文本, 代际号)
    response_ready = Signal(str, int)  # (完整回复文本, 代际号)
    failed = Signal(str, int)          # (错误信息, 代际号)

    def __init__(self, agent: ChessAgent, request: AgentRequest, generation: int = 0, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.request = request
        self.generation = generation
        self._is_cancelled = False
        # 线程结束自动回收 C++ / Python 资源，防止长时间对局产生对象累积泄漏
        self.finished.connect(self.deleteLater)

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            def _on_chunk(chunk: str):
                if not self._is_cancelled:
                    self.chunk_ready.emit(chunk, self.generation)

            def _check_cancelled() -> bool:
                return self._is_cancelled

            # 依据实际签名决定是否传递取消回调 (稳健于接口差异)
            params = inspect.signature(self.agent.reply).parameters
            if "is_cancelled" in params:
                reply = self.agent.reply(self.request, on_chunk=_on_chunk, is_cancelled=_check_cancelled)
            else:
                reply = self.agent.reply(self.request, on_chunk=_on_chunk)

            if not self._is_cancelled:
                self.response_ready.emit(reply, self.generation)
        except Exception as e:
            logger.error("LLMWorker 执行失败: %s", e, exc_info=True)
            if not self._is_cancelled:
                self.failed.emit(str(e), self.generation)


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
        # 双层记忆系统
        self.short_memory = ShortTermMemory(max_turns=12)
        self.long_memory = LongTermMemory()
        # 语义缓存: 同局面+同教学开关的确定性请求直接复用回复 (自动教学/主动询问)
        self._semantic_cache = SemanticCache(maxsize=128)
        self._pending_cache_key: Optional[str] = None
        # 加载持久化配置
        self._persisted_config = self._load_persisted_settings()
        # 当前生效的人设 Prompt (可被用户通过「人设」按钮运行时修改)
        self.current_persona = self._persisted_config.get("persona") or DEFAULT_MAID_PERSONA
        # 默认使用 LLMAgent (优先使用持久化配置)
        llm_cfg = self._persisted_config.get("llm", {})
        self.controller.search_api_url = llm_cfg.get("search_api_url", "")
        self.controller.search_api_key = llm_cfg.get("search_api_key", "")
        if agent is None:
            self.agent = LLMAgent(
                api_base=llm_cfg.get("api_base") or None,
                api_key=llm_cfg.get("api_key") or None,
                model=llm_cfg.get("model") or None,
                reasoning_effort=llm_cfg.get("reasoning_effort") or None,
                stream=llm_cfg.get("stream", False),
                persona_prompt=self.current_persona,
            )
        else:
            self.agent = agent
            if isinstance(self.agent, LLMAgent):
                if not self.agent.api_key and llm_cfg.get("api_key"):
                    self.agent.api_key = llm_cfg.get("api_key")
                if self.agent.api_base == "https://api.deepseek.com" and llm_cfg.get("api_base"):
                    self.agent.api_base = llm_cfg["api_base"]
                if self.agent.model in ("deepseek-chat", "deepseek-v4-flash") and llm_cfg.get("model"):
                    self.agent.model = llm_cfg["model"]
                if llm_cfg.get("reasoning_effort"):
                    self.agent.reasoning_effort = llm_cfg.get("reasoning_effort")
                if "stream" in llm_cfg:
                    self.agent.stream = bool(llm_cfg["stream"])
        if isinstance(self.agent, LLMAgent) and "show_tool_records" in llm_cfg:
            self.agent.show_tool_records = bool(llm_cfg["show_tool_records"])

        self.controller.set_agent(self.agent)
        self._llm_thread: Optional[LLMWorker] = None
        self._llm_generation = 0  # LLM 请求代际号: 新请求发出后, 旧线程的过期回复按代际丢弃
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

        # 1. 顶部控制栏 (现代极简风格)
        self.control_bar = ControlBar(self)
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
        main_layout.addWidget(self.control_bar)

        # 固定横向边界：约束顶部控制栏与三栏工作区，不参与拖拽。
        toolbar_boundary = QFrame(self)
        toolbar_boundary.setObjectName("toolbarBoundary")
        toolbar_boundary.setFixedHeight(2)
        toolbar_boundary.setFrameShape(QFrame.HLine)
        toolbar_boundary.setStyleSheet("background-color: #334155; border: none;")
        main_layout.addWidget(toolbar_boundary)

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
        board_widget = QWidget(self.content_splitter)
        board_container = QVBoxLayout(board_widget)
        board_container.setContentsMargins(8, 0, 8, 0)
        board_container.setAlignment(Qt.AlignCenter)
        self.status_bar_label = QLabel("当前行动: 白方 (White)")
        self.status_bar_label.setAlignment(Qt.AlignCenter)
        self.status_bar_label.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: 700; padding: 4px;")
        board_container.addWidget(self.status_bar_label)

        self.chess_board = ChessBoardWidget(self.controller.board_state, board_widget)
        self.chess_board.allowed_side_callback = self._get_user_allowed_color
        self.chess_board.move_ready.connect(self.controller.apply_move)
        board_container.addWidget(self.chess_board, alignment=Qt.AlignCenter)
        board_widget.setMinimumWidth(self.chess_board.minimumSizeHint().width() + 16)
        self.content_splitter.addWidget(board_widget)

        # [右侧]：LLM 女仆互动对话窗口
        self.chat_panel = ChatPanel(self.content_splitter)
        self.chat_panel.setMinimumWidth(260)
        self.chat_panel.message_sent.connect(self.on_user_chat_message)
        self.chat_panel.ask_llm_requested.connect(self.on_ask_llm_requested)
        self.content_splitter.addWidget(self.chat_panel)

        # 默认比例接近原布局；之后可拖动任一竖线自由调整相邻区域宽度。
        self.content_splitter.setStretchFactor(0, 0)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setStretchFactor(2, 1)
        self.content_splitter.setSizes([240, 560, 440])
        main_layout.addWidget(self.content_splitter, stretch=1)

    def _get_user_allowed_color(self) -> Optional[chess.Color]:
        """判定当前模式下玩家允许操控的棋子颜色，非对弈模式或本地双人模式返回 None (允许操控双方)"""
        mode = self.controller.modes.mode
        if mode in (GameMode.VS_ENGINE, GameMode.VS_MAID_LLM):
            return chess.WHITE if self.controller.modes.player_side == "white" else chess.BLACK
        if mode == GameMode.ONLINE_PVP and self._online_client:
            return chess.WHITE if self._online_client.my_side == "white" else chess.BLACK
        return None

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
        ctrl.undo_requested_by_llm.connect(self.on_llm_undo_requested)
        ctrl.llm_fallback_used.connect(self.on_llm_fallback_used)

    def _generate_llm_summary(self, snapshot, result_str: str = "*") -> str:
        """为终局持久化生成高质量的 LLM 战术复盘总结报告 (两段式: 教练分析 -> 女仆改写)

        在后台归档线程执行:
          - 全盘着法质量评估在记录深拷贝副本上运行, 不与 UI 线程竞态
          - 评估结果同步回填长期记忆画像 (开局偏好 / 失误类型), 激活画像档案
        """
        evaluated_moves = []
        try:
            records_copy = copy.deepcopy(self.controller.history.records)
            evaluated_moves = self.controller.evaluate_game_moves_quality(depth=8, records=records_copy)
        except Exception as e:
            logger.warning("全盘着法质量评估失败: %s", e, exc_info=True)

        blunders = [m for m in evaluated_moves if m.get("quality") in ("Blunder", "Mistake")]

        # 长期画像回填: 开局名称 (开局库识别) + 失误着法标签
        opening_name = None
        try:
            info = self.controller.history_store.opening_book.query_opening(snapshot.fen)
            if isinstance(info, dict) and info.get("in_book"):
                name = info.get("name")
                if name and name != "Unknown Opening":
                    opening_name = name
        except Exception:
            opening_name = None
        try:
            self.long_memory.record_game_result(
                result=result_str,
                opening=opening_name,
                blunders=[f"{b['move']}({b['quality']})" for b in blunders[:5]],
            )
            if blunders:
                worst_blunder = min(blunders, key=lambda x: x.get("delta_cp", 0))
                self.long_memory.record_distilled_insight(
                    weakness=f"第 {worst_blunder['ply']} 半回合漏着 {worst_blunder['move']} (损失 {worst_blunder['delta_cp']}cp)",
                    advice="在中后局行棋前需重点复核潜在战术战机与王翼安全防护"
                )
        except Exception as e:
            logger.warning("长期画像回填与蒸馏失败: %s", e)

        blunder_summary = ""
        if blunders:
            b_lines = [f"- 第 {b['ply']} 半回合 ({b['turn']} 走 {b['move']}): 判定为 {b['quality']} (评估损失 {b['delta_cp']} cp)" for b in blunders[:4]]
            blunder_summary = "\n【引擎全盘复盘关键转折与失误点】：\n" + "\n".join(b_lines)

        custom_prompt = PromptBuilder.build_custom_prompt(
            snapshot=snapshot,
            triggers=self.controller.teaching,
            is_auto_move=False,
            extra_note=f"本局已终局，请为对局归档提供精准全面的 Coach 战术复盘总结。{blunder_summary}\n{self.long_memory.get_summary_prompt()}",
        )
        req = self.controller.build_agent_request(
            user_message=custom_prompt,
            persona_prompt=self.current_persona,
            dialog_history=self.short_memory.get_messages(),
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

    def on_llm_fallback_used(self, source: str):
        """LLM 走棋不可用、由引擎降级代走时的非阻断披露"""
        self.chat_panel.append_maid_message(f"*(LLM 走棋暂不可用，本步已由 {source} 引擎代走)*")

    def on_llm_undo_requested(self, reason: str):
        """处理 LLM 劣势时向玩家发送的悔棋请求 (非模态: 不打断引擎思考与事件循环)"""
        self.chat_panel.append_maid_message(
            f"**女仆悔棋请求**：{reason}\n主人可以点击上方「悔棋」按钮体贴一下女仆哦～"
        )

    def on_move_played(self, san: str, uci: str, was_white: bool):
        """
        若教学模块打开 (master_enabled 为 True)，人类玩家走一步棋，LLM 保证回应一步教学
        """
        if self._online_client and self.controller.modes.mode == GameMode.ONLINE_PVP:
            # 判断这步是否是自己走的，如果是则同步发送给服务端
            is_my_move = (was_white and self._online_client.my_side == "white") or (not was_white and self._online_client.my_side == "black")
            if is_my_move:
                self._online_client.send_move(uci, self.controller.get_fen())

        triggers = self.controller.teaching
        if not triggers.master_enabled or not self._has_configured_llm_api():
            return

        # 针对人类玩家本人的走棋触发教学指导
        if self.controller.modes.mode in (GameMode.VS_ENGINE, GameMode.VS_MAID_LLM):
            player_is_white = (self.controller.modes.player_side == "white")
            if was_white != player_is_white:
                return
        elif self.controller.modes.mode == GameMode.ONLINE_PVP:
            if not is_my_move:
                return

        # 构建内部教学 prompt，玩家走一步棋即回应一步
        snapshot = self.controller.get_snapshot()
        model_name = getattr(self.agent, "model", "")
        cache_key = SemanticCache.make_key(
            "auto_teach", snapshot.fen,
            triggers.master_enabled, triggers.eval_current_position,
            triggers.suggest_moves, triggers.eval_history_moves,
            triggers.game_over_summary, self.controller.modes.mode.value,
            self.current_persona, model_name,
        )
        custom_prompt = PromptBuilder.build_custom_prompt(
            snapshot=snapshot,
            triggers=triggers,
            is_auto_move=True,
            extra_note=f"玩家刚刚走出了着法 `{san}`。请立即结合当下棋盘局势与失误预警，给出一对一陪练指导。",
            game_mode_name=self.controller.modes.mode.value,
        )
        self._dispatch_llm_request(
            custom_prompt,
            memory_label=f"[落子自动教学] 最近一步 {san}",
            cache_key=cache_key,
        )

    def on_game_over(self, status: dict):
        result = status.get("result", "*")
        reason = status.get("reason", "")
        # 长期画像 (开局/失误) 由 _generate_llm_summary 在归档线程结合评估结果统一回填
        self.chat_panel.append_maid_message(f"**对局结束！**<br>结果: `{result}` - {reason}")
        QMessageBox.information(self, "对局结束", f"结果: {result}\n原因: {reason}")

    def on_game_reset(self):
        self.short_memory.clear()
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
            side_dialog.addButton("执白 (先手)", QMessageBox.ActionRole)
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
            # 默认仅绑定回环地址; 如需局域网对战, 由用户在对话框中显式输入 0.0.0.0
            bind_host = host if host else "127.0.0.1"
            self._online_server = EmbeddedOnlineServer(host=bind_host, port=port)
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
            return

        # 若该步为悔棋，将“玩家选择悔棋”信息打包发送给LLM
        triggers = self.controller.teaching
        if triggers.master_enabled and self._has_configured_llm_api():
            snapshot = self.controller.get_snapshot()
            custom_prompt = PromptBuilder.build_custom_prompt(
                snapshot=snapshot,
                triggers=triggers,
                is_auto_move=True,
                extra_note="【玩家选择悔棋】玩家刚刚执行了悔棋操作，回退了之前的走法。请结合回退后的最新局面提供后续思路与指导建议。",
                game_mode_name=self.controller.modes.mode.value,
            )
            self._dispatch_llm_request(
                custom_prompt,
                memory_label="[悔棋] 玩家回退了最近走法",
            )

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
        if hasattr(self, "history_panel"):
            self.history_panel.apply_theme(is_light)

        if theme_name == "浅色":
            self.setStyleSheet("""
                QMainWindow { background-color: #f8fafc; }
                QWidget { color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
                QMessageBox, QInputDialog, QDialog { background-color: #ffffff; color: #0f172a; }
                QMessageBox QPushButton, QInputDialog QPushButton, QDialog QPushButton { background-color: #e2e8f0; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 5px 12px; }
                QMessageBox QLabel, QInputDialog QLabel, QDialog QLabel { color: #0f172a; }
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
                QMessageBox, QInputDialog, QDialog { background-color: #1e222d; color: #f1f5f9; }
                QMessageBox QPushButton, QInputDialog QPushButton, QDialog QPushButton { background-color: #334155; color: #ffffff; border: 1px solid #475569; border-radius: 4px; padding: 5px 12px; }
                QMessageBox QLabel, QInputDialog QLabel, QDialog QLabel { color: #f1f5f9; }
                QTableWidget { background-color: #0f172a; color: #e2e8f0; gridline-color: #1e293b; border: 1px solid #1e293b; }
                QHeaderView::section { background-color: #1e293b; color: #94a3b8; border-bottom: 1px solid #334155; }
                QTextBrowser { background-color: #0b0f19; color: #e2e8f0; border: 1px solid #1e293b; }
                QLineEdit { background-color: #111827; color: #f8fafc; border: 1px solid #334155; }
            """)
        else: # 跟随系统
            self.setStyleSheet("""
                QMainWindow { background-color: #0b0f19; }
                QWidget { color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
                QMessageBox, QInputDialog, QDialog { background-color: #1e222d; color: #f1f5f9; }
                QMessageBox QPushButton, QInputDialog QPushButton, QDialog QPushButton { background-color: #334155; color: #ffffff; border: 1px solid #475569; border-radius: 4px; padding: 5px 12px; }
                QMessageBox QLabel, QInputDialog QLabel, QDialog QLabel { color: #f1f5f9; }
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
        if "custom_personas" in new_config:
            if "llm" not in self._persisted_config:
                self._persisted_config["llm"] = {}
            self._persisted_config["llm"]["custom_personas"] = new_config["custom_personas"]

        self.controller.set_agent(self.agent)
        self._sync_llm_connection_status()
        self._save_persisted_settings()

        QMessageBox.information(
            self, "AI 设置已保存",
            "已成功更新 AI 连接配置、联网搜索接口、教学触发器与人设！"
        )

    def _collect_current_llm_config(self) -> dict:
        """从当前 agent 收集配置, 用于预填配置对话框"""
        custom_personas = self._persisted_config.get("llm", {}).get("custom_personas", [])
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
                "custom_personas": custom_personas,
            }
        return {
            "search_api_url": getattr(self.controller, "search_api_url", ""),
            "search_api_key": getattr(self.controller, "search_api_key", ""),
            "custom_personas": custom_personas,
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
            try:
                # 严格限制凭据配置文件仅当前用户可读写 (600 权限)，保障本地存储安全
                os.chmod(CONFIG_FILE_PATH, 0o600)
            except Exception:
                pass
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
        要求4：主动询问 LLM 按钮触发的定制 prompt (接入语义缓存)
        """
        triggers = self.controller.teaching
        snapshot = self.controller.get_snapshot()
        model_name = getattr(self.agent, "model", "")
        cache_key = SemanticCache.make_key(
            "ask_llm", snapshot.fen,
            triggers.master_enabled, triggers.eval_current_position,
            triggers.suggest_moves, triggers.eval_history_moves,
            triggers.game_over_summary, self.controller.modes.mode.value,
            self.current_persona, model_name,
        )
        custom_prompt = PromptBuilder.build_custom_prompt(
            snapshot=snapshot,
            triggers=triggers,
            is_auto_move=False,
            game_mode_name=self.controller.modes.mode.value,
        )
        self.chat_panel.append_user_message("*(点击了「主动询问女仆指导」)*")
        self._dispatch_llm_request(
            custom_prompt,
            memory_label="[主动询问] 全局局势指导",
            cache_key=cache_key,
        )

    def on_user_chat_message(self, message: str):
        """手动输入框发送消息 (用户自由输入, 走 untrusted 防注入包裹)"""
        self._dispatch_llm_request(message, trusted=False)

    def _dispatch_llm_request(
        self,
        message: str,
        memory_label: Optional[str] = None,
        cache_key: Optional[str] = None,
        trusted: bool = True,
    ):
        """异步调度 LLM 请求，展示 Loading 旋转控件与逐字打字机流式渲染

        Token 工程化:
          - 语义缓存命中: 直接复用回复, 零网络请求
          - 短期记忆只写入意图标签 (memory_label) 而非含完整 PGN 的提示词
          - trusted=False 时用户原文以 <untrusted_user_input> 包裹发送, 防 Prompt 注入
        """
        # 取消上一个在途的 LLM 线程
        if self._llm_thread is not None and self._llm_thread.isRunning():
            self._llm_thread.cancel()

        self._llm_generation += 1
        generation = self._llm_generation
        self._pending_cache_key = None

        fen = self.controller.get_fen()
        label = memory_label or message

        # 语义缓存命中: 记忆落账 + 直接展示
        if cache_key:
            cached = self._semantic_cache.get(cache_key)
            if cached:
                logger.debug("语义缓存命中: %s", cache_key[:12])
                self.short_memory.add_turn(role="user", content=label, fen=fen)
                self.short_memory.add_turn(role="assistant", content=cached, fen=fen)
                self.chat_panel.append_maid_message(cached)
                return

        self._pending_cache_key = cache_key
        self.chat_panel.set_loading(True)
        # 记录用户意图标签 (而非完整 Prompt) 到短期工作记忆, 避免历史上下文 PGN 膨胀
        self.short_memory.add_turn(role="user", content=label, fen=fen)

        request = self.controller.build_agent_request(
            message,
            persona_prompt=self.current_persona,
            dialog_history=self.short_memory.get_messages()[:-1],  # 传入历史上下文
            player_profile_summary=self.long_memory.get_summary_prompt() if getattr(self, "long_memory", None) else None,
        )
        request.trust_user_message = trusted

        self._llm_thread = LLMWorker(self.agent, request, generation=generation, parent=self)
        self._llm_thread.chunk_ready.connect(self._on_llm_chunk)
        self._llm_thread.response_ready.connect(self._on_llm_response)
        self._llm_thread.failed.connect(self._on_llm_failed)
        self._llm_thread.start()

    def _on_llm_chunk(self, chunk: str, generation: int):
        if generation != self._llm_generation:
            return
        self.chat_panel.append_maid_chunk(chunk)

    def _on_llm_response(self, reply: str, generation: int):
        if generation != self._llm_generation:
            return  # 过期回复, 丢弃
        self.chat_panel.set_loading(False)
        self.chat_panel.finalize_maid_stream(reply)
        # 记录女仆回复到短期记忆; 命中语义缓存键的确定性回复写入缓存
        if reply:
            self.short_memory.add_turn(role="assistant", content=reply, fen=self.controller.get_fen())
            if self._pending_cache_key:
                self._semantic_cache.put(self._pending_cache_key, reply)
        self._pending_cache_key = None
        # 用量可观测性: 输出累计 Token/调用统计
        if isinstance(self.agent, LLMAgent):
            logger.info("LLM 用量统计: %s", self.agent.get_usage_stats())

    def _on_llm_failed(self, error_msg: str, generation: int):
        if generation != self._llm_generation:
            return
        self.chat_panel.set_loading(False)
        self._pending_cache_key = None  # 失败回复不入缓存
        self.chat_panel.finalize_maid_stream(f"*(女仆回复出现异常: {error_msg})*")
