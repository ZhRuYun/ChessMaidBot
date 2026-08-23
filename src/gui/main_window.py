"""
主窗口 (模块1 - GUI 装配层)
负责协调 UI 布局（左侧:记谱表，中央:棋盘，右侧:LLM 对话窗口）
处理用户交互（新对局、悔棋、翻转、认输、求和、一键导出 PGN+FEN、主动询问LLM、落子自动触发教学）
"""
from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QMessageBox, QApplication
)
from PySide6.QtCore import QThread, Signal
import chess

from ..agents.base import ChessAgent, AgentRequest
from ..agents.llm_agent import LLMAgent
from ..agents.prompt_builder import PromptBuilder
from ..config import DEFAULT_MAID_PERSONA
from ..controller.game_controller import GameController
from .chess_board import ChessBoardWidget
from .move_history_panel import MoveHistoryPanel
from .chat_panel import ChatPanel
from .control_bar import ControlBar


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
        # 当前生效的人设 Prompt (可被用户通过「🎭 人设」按钮运行时修改)
        self.current_persona = DEFAULT_MAID_PERSONA
        # 默认使用 LLMAgent (无 API Key 时自动降级为本地描述性回复, 行为同 EchoAgent)
        self.agent = agent or LLMAgent(persona_prompt=self.current_persona)
        self._llm_thread: Optional[LLMWorker] = None

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
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(12)

        # 1. 顶部控制栏 (现代极简暗黑风格)
        self.control_bar = ControlBar(self)
        self.control_bar.new_game_requested.connect(self.on_new_game)
        self.control_bar.undo_requested.connect(self.on_undo)
        self.control_bar.flip_requested.connect(self.on_flip)
        self.control_bar.resign_requested.connect(self.on_resign)
        self.control_bar.draw_requested.connect(self.on_draw)
        self.control_bar.export_state_requested.connect(self.on_export_game_state)
        self.control_bar.llm_config_requested.connect(self.on_open_llm_config)
        self.control_bar.persona_config_requested.connect(self.on_open_persona_config)
        self.control_bar.mode_changed.connect(self.controller.set_mode_label)
        self.control_bar.elo_changed.connect(self.controller.set_engine_elo)
        main_layout.addWidget(self.control_bar)

        # 2. 中间核心区：左侧记谱表 + 中央棋盘 + 右侧LLM对话 (三栏现代极简布局)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # [左侧]：走法历史双栏记谱表
        history_container = QVBoxLayout()
        history_title = QLabel("📜 走法记谱 (Moves)")
        history_title.setStyleSheet("color: #94a3b8; font-weight: 700; font-size: 13px; padding-bottom: 2px;")
        history_container.addWidget(history_title)

        self.history_panel = MoveHistoryPanel(self)
        self.history_panel.setFixedWidth(240)
        history_container.addWidget(self.history_panel)
        content_layout.addLayout(history_container)

        # [中央]：棋盘区域 + 行动与将军状态指示
        board_container = QVBoxLayout()
        self.status_bar_label = QLabel("当前行动: 白方 (White)")
        self.status_bar_label.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: 700; padding: 4px;")
        board_container.addWidget(self.status_bar_label)

        self.chess_board = ChessBoardWidget(self.controller.board_state, self)
        self.chess_board.move_ready.connect(self.controller.apply_move)
        board_container.addWidget(self.chess_board)
        content_layout.addLayout(board_container)

        # [右侧]：LLM 女仆互动对话窗口
        self.chat_panel = ChatPanel(self.controller.teaching, self)
        self.chat_panel.message_sent.connect(self.on_user_chat_message)
        self.chat_panel.ask_llm_requested.connect(self.on_ask_llm_requested)
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
            self.status_bar_label.setText("🤖 Stockfish 深度思考中...")
            self.status_bar_label.setStyleSheet("color: #fbbf24; font-size: 14px; font-weight: 700; padding: 4px;")
            self.chess_board.setEnabled(False)
        else:
            self.chess_board.setEnabled(True)

    def on_move_played(self, san: str, uci: str, was_white: bool):
        """
        要求2：若总开关开启，玩家每走一步棋，根据棋盘现状信息 (PGN, FEN) 和 4 个子开关启动情况，
        向 LLM 发送定制 prompt 并等待回复 (异步 + loading 转圈动效)
        """
        triggers = self.controller.teaching
        if not triggers.master_enabled:
            return

        # 构建定制 prompt
        snapshot = self.controller.get_snapshot()
        custom_prompt = PromptBuilder.build_custom_prompt(
            snapshot=snapshot,
            triggers=triggers,
            is_auto_move=True,
        )

        side_cn = "白方" if was_white else "黑方"
        self.chat_panel.append_user_message(f"*(落子: {side_cn} `{san}` - 触发教学分析)*")
        self._dispatch_llm_request(custom_prompt)

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

    # ---------- AI 女仆连接配置 ----------

    def on_open_llm_config(self):
        """打开 LLM 配置对话框, 应用后重建 LLMAgent 并更新状态徽章"""
        # 收集当前 agent 配置用于预填表单
        current_config = self._collect_current_llm_config()
        from .llm_config_dialog import LLMConfigDialog
        new_config = LLMConfigDialog.get_config_dialog(
            current_config=current_config, parent=self
        )
        if new_config is None:
            return  # 用户取消

        # 重建 LLMAgent (保留当前人设, 应用新配置)
        self.agent = LLMAgent(
            api_base=new_config.get("api_base") or None,
            api_key=new_config.get("api_key") or None,
            model=new_config.get("model") or None,
            reasoning_effort=new_config.get("reasoning_effort") or None,
            stream=new_config.get("stream", False),
            persona_prompt=self.current_persona,
        )
        self._sync_llm_connection_status()

        # 友好的反馈提示
        if self.agent.api_key:
            QMessageBox.information(
                self, "AI 女仆已连接",
                f"已成功配置 AI 女仆连接！\n\n模型: {self.agent.model}\n基地址: {self.agent.api_base}\n"
                f"思考档位: {self.agent.reasoning_effort}\n流式输出: {'开启' if self.agent.stream else '关闭'}\n\n"
                f"现在 ChessMaid 将使用真实大语言模型进行棋艺教学。"
            )
        else:
            QMessageBox.information(
                self, "已切换为本地降级模式",
                "未填写 API Key, ChessMaid 将使用本地降级回复。\n\n"
                "如需接入真实 AI, 请点击「⚙️ AI 设置」填入 API Key。"
            )

    def _collect_current_llm_config(self) -> dict:
        """从当前 agent 收集配置, 用于预填配置对话框"""
        if isinstance(self.agent, LLMAgent):
            return {
                "api_base": self.agent.api_base,
                "api_key": self.agent.api_key,
                "model": self.agent.model,
                "reasoning_effort": self.agent.reasoning_effort,
                "stream": self.agent.stream,
            }
        return {}

    def _sync_llm_connection_status(self):
        """根据当前 agent 的 Key 配置, 同步 chat_panel 状态徽章"""
        if isinstance(self.agent, LLMAgent):
            connected = bool(self.agent.api_key)
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
