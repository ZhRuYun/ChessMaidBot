"""
LLM 女仆互动对话面板 (模块1 - GUI)
- 现代化极简黑曜石设计
- 教学开关直接读写调度层的 TeachingTriggers 配置对象
- 包含 Loading Spinner 转圈动效展示
- 提供"主动询问LLM"按钮及手动输入提问链路
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QLineEdit, QPushButton, QLabel, QGroupBox, QCheckBox, QFrame
)
from PySide6.QtCore import Signal
import markdown

from ..controller.teaching_triggers import TeachingTriggers
from .loading_spinner import LoadingSpinner


class ChatPanel(QWidget):
    message_sent = Signal(str)
    ask_llm_requested = Signal()
    teaching_triggers_changed = Signal(object)

    def __init__(self, triggers: TeachingTriggers, parent=None):
        super().__init__(parent)
        self.triggers = triggers

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. 顶部女仆状态标头 + Loading 转圈指示器
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.avatar_label = QLabel("♟️")
        self.avatar_label.setStyleSheet("font-size: 20px;")

        self.title_label = QLabel("ChessMaid 教学助手")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")

        # Loading Spinner 旋转动效
        self.spinner = LoadingSpinner(self, size=20, color="#38bdf8")
        self.spinner.hide()

        self.status_badge = QLabel("● 在线")
        self.status_badge.setStyleSheet("color: #10b981; font-size: 12px; font-weight: 600;")

        header_layout.addWidget(self.avatar_label)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.spinner)
        header_layout.addStretch()
        header_layout.addWidget(self.status_badge)
        layout.addLayout(header_layout)

        # 2. 教学触发器控制组 (1个总开关 + 4个细分开关) - 极简卡片式
        teaching_box = QGroupBox("🤖 教学触发器配置")
        teaching_box.setStyleSheet("""
            QGroupBox {
                color: #38bdf8;
                font-weight: 600;
                font-size: 12px;
                border: 1px solid #27354a;
                border-radius: 8px;
                background-color: #111827;
                margin-top: 6px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QCheckBox {
                color: #cbd5e1;
                font-size: 12px;
                spacing: 6px;
            }
            QCheckBox:hover {
                color: #f8fafc;
            }
            QCheckBox:disabled {
                color: #475569;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #475569;
                background-color: #1e293b;
            }
            QCheckBox::indicator:checked {
                background-color: #38bdf8;
                border-color: #38bdf8;
            }
        """)
        t_layout = QVBoxLayout(teaching_box)
        t_layout.setSpacing(6)
        t_layout.setContentsMargins(10, 8, 10, 8)

        # 总开关 (Master Switch)
        self.chk_master = QCheckBox("【总开关】开启每步自动教学")
        self.chk_master.setChecked(self.triggers.master_enabled)
        self.chk_master.setStyleSheet("color: #38bdf8; font-weight: 700;")
        self.chk_master.toggled.connect(self._on_master_toggled)
        t_layout.addWidget(self.chk_master)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #1e293b;")
        t_layout.addWidget(line)

        # 4个细分触发开关
        sub_layout = QVBoxLayout()
        sub_layout.setContentsMargins(10, 0, 0, 0)
        sub_layout.setSpacing(4)

        self.chk_eval_pos = QCheckBox("1. 当下局面评估 (优劣势与子力)")
        self.chk_suggest_moves = QCheckBox("2. 建议着法评估 (候选着法思路)")
        self.chk_eval_history = QCheckBox("3. 历史走法评估 (失误预警)")
        self.chk_summary = QCheckBox("4. 棋局结束总结 (赛后复盘)")

        self._sub_checks = [
            (self.chk_eval_pos, "eval_current_position"),
            (self.chk_suggest_moves, "suggest_moves"),
            (self.chk_eval_history, "eval_history_moves"),
            (self.chk_summary, "game_over_summary"),
        ]
        for chk, attr in self._sub_checks:
            chk.setChecked(getattr(self.triggers, attr))
            chk.toggled.connect(self._update_triggers)
            sub_layout.addWidget(chk)

        t_layout.addLayout(sub_layout)
        layout.addWidget(teaching_box)
        self._on_master_toggled(self.triggers.master_enabled)

        # 3. 消息展示区 (现代深色气泡流)
        self.chat_display = QTextBrowser(self)
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setStyleSheet("""
            QTextBrowser {
                background-color: #0b0f19;
                color: #e2e8f0;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(self.chat_display)

        # 4. "主动询问LLM" 快捷交互按钮条
        ask_bar_layout = QHBoxLayout()
        self.ask_llm_btn = QPushButton("✨ 主动询问女仆指导 (分析当前局势)", self)
        self.ask_llm_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: #ffffff;
                border-color: #38bdf8;
            }
            QPushButton:pressed {
                background-color: #075985;
            }
            QPushButton:disabled {
                background-color: #111827;
                color: #475569;
                border-color: #1e293b;
            }
        """)
        self.ask_llm_btn.clicked.connect(self.ask_llm_requested.emit)
        ask_bar_layout.addWidget(self.ask_llm_btn)
        layout.addLayout(ask_bar_layout)

        # 5. 底部输入框与发送按钮
        input_layout = QHBoxLayout()
        input_layout.setSpacing(6)

        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("向女仆请教国际象棋战术或输入问题...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #111827;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
        """)
        self.input_field.returnPressed.connect(self._send_message)

        self.send_btn = QPushButton("发送", self)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #475569;
            }
        """)
        self.send_btn.clicked.connect(self._send_message)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        layout.addLayout(input_layout)

    # ---------- 对外状态方法 ----------

    def set_loading(self, loading: bool):
        """控制转圈动效与控件可点击状态"""
        if loading:
            self.spinner.start()
            self.status_badge.setText("● 思考中...")
            self.status_badge.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 600;")
            self.ask_llm_btn.setEnabled(False)
            self.send_btn.setEnabled(False)
        else:
            self.spinner.stop()
            self._restore_status_badge()
            self.ask_llm_btn.setEnabled(True)
            self.send_btn.setEnabled(True)

    def set_llm_connected(self, connected: bool, model: str = ""):
        """更新女仆连接状态徽章 (供 MainWindow 在配置变更后调用)

        Args:
            connected: True=已接入真实 LLM (绿色在线); False=本地降级 (橙色)
            model: 已接入时显示的模型名称, 用于状态栏提示
        """
        self._llm_connected = connected
        self._llm_model_hint = model if connected else ""
        if connected:
            self.status_badge.setText(f"● LLM 在线{f' · {model}' if model else ''}")
            self.status_badge.setStyleSheet("color: #10b981; font-size: 12px; font-weight: 600;")
        else:
            self.status_badge.setText("● 本地降级")
            self.status_badge.setStyleSheet("color: #fbbf24; font-size: 12px; font-weight: 600;")

    def _restore_status_badge(self):
        """恢复状态徽章为当前连接状态 (loading 结束后调用)"""
        if getattr(self, "_llm_connected", False):
            self.set_llm_connected(True, getattr(self, "_llm_model_hint", ""))
        else:
            self.set_llm_connected(False)

    # ---------- 教学触发器槽 ----------

    def _on_master_toggled(self, checked: bool):
        for chk, _attr in self._sub_checks:
            chk.setEnabled(checked)
        self._update_triggers()

    def _update_triggers(self):
        self.triggers.master_enabled = self.chk_master.isChecked()
        for chk, attr in self._sub_checks:
            setattr(self.triggers, attr, chk.isChecked())
        self.teaching_triggers_changed.emit(self.triggers)

    # ---------- 消息流 ----------

    def send_message(self, text: str):
        """统一消息入口: 显示用户气泡并广播消息信号"""
        text = text.strip()
        if not text:
            return
        self.append_user_message(text)
        self.message_sent.emit(text)

    def append_user_message(self, text: str):
        html = f"""
        <div style='margin-bottom: 12px; text-align: right;'>
            <div style='display: inline-block; background-color: #1e293b; color: #f8fafc; padding: 8px 12px; border-radius: 10px 10px 2px 10px; border: 1px solid #334155; max-width: 85%; text-align: left;'>
                <b style='color: #94a3b8; font-size: 11px;'>👤 您:</b><br>{text}
            </div>
        </div>
        """
        self.chat_display.append(html)

    def append_maid_message(self, text: str):
        md_html = markdown.markdown(text, extensions=['extra'])
        html = f"""
        <div style='margin-bottom: 12px; text-align: left;'>
            <div style='display: inline-block; background-color: #111827; color: #e2e8f0; padding: 8px 12px; border-radius: 10px 10px 10px 2px; border-left: 3px solid #38bdf8; border-top: 1px solid #1e293b; border-right: 1px solid #1e293b; border-bottom: 1px solid #1e293b; max-width: 92%;'>
                <span style='color: #38bdf8; font-weight: 700; font-size: 11px;'>♟️ ChessMaid:</span><br>{md_html}
            </div>
        </div>
        """
        self.chat_display.append(html)

    def _send_message(self):
        text = self.input_field.text()
        if not text.strip():
            return
        self.input_field.clear()
        self.send_message(text)
