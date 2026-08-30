"""
LLM 女仆互动对话面板 (模块1 - GUI)
- 现代化极简设计
- 包含 Loading Spinner 转圈动效展示
- 提供"主动询问LLM"按钮及手动输入提问链路
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QLineEdit, QPushButton, QLabel
)
from PySide6.QtCore import Signal
import markdown

from .loading_spinner import LoadingSpinner


class ChatPanel(QWidget):
    message_sent = Signal(str)
    ask_llm_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. 顶部状态标头 + Loading 转圈指示器
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.title_label = QLabel("ChessMaid 教学助手")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")

        # Loading Spinner 旋转动效
        self.spinner = LoadingSpinner(self, size=20, color="#38bdf8")
        self.spinner.hide()

        self.status_badge = QLabel("● 在线")
        self.status_badge.setStyleSheet("color: #10b981; font-size: 12px; font-weight: 600;")

        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.spinner)
        header_layout.addStretch()
        header_layout.addWidget(self.status_badge)
        layout.addLayout(header_layout)

        # 2. 消息展示区 (现代深色气泡流)
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
            }
        """)
        layout.addWidget(self.chat_display, stretch=1)

        # 3. 底部交互区: 主动询问按钮 + 文本输入框
        action_layout = QVBoxLayout()
        action_layout.setSpacing(8)

        self.ask_llm_btn = QPushButton("✨ 主动询问女仆指导 (分析局势与候选着法)", self)
        self.ask_llm_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 9px 14px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton:pressed {
                background-color: #075985;
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #64748b;
            }
        """)
        self.ask_llm_btn.clicked.connect(self.ask_llm_requested.emit)
        action_layout.addWidget(self.ask_llm_btn)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)

        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("向女仆提问 (例如: '这步走 d4 有什么战略意图？')...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #111827;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 9px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #38bdf8;
            }
        """)
        self.input_field.returnPressed.connect(self._send_message)

        self.send_btn = QPushButton("发送", self)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 9px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #64748b;
            }
        """)
        self.send_btn.clicked.connect(self._send_message)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        action_layout.addLayout(input_layout)

        layout.addLayout(action_layout)

        self._message_history: list[tuple[str, str]] = []  # (role, text/markdown)

        # 初始欢迎信息
        self.append_maid_message(
            "主人您好！我是您的 AI 棋艺教学助理【ChessMaid】。\n\n"
            "我已为您准备好棋盘。您可以在上方点击「AI 设置」配置真实模型 API、调节教学触发器以及人设风格。"
        )

    def set_loading(self, loading: bool):
        """设置思考/加载动画状态，防止重复提交"""
        if loading:
            self.spinner.show()
            self.spinner.start()
            self.status_badge.setText("● 思考中...")
            self.status_badge.setStyleSheet("color: #fbbf24; font-size: 12px; font-weight: 600;")
            self.ask_llm_btn.setEnabled(False)
            self.send_btn.setEnabled(False)
            self.input_field.setEnabled(False)
        else:
            self.spinner.stop()
            self.spinner.hide()
            self.ask_llm_btn.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.input_field.setEnabled(True)
            self._restore_status_badge()

    def set_llm_connected(self, connected: bool, model: str = ""):
        """更新在线/本地降级徽章状态"""
        self._llm_connected = connected
        self._llm_model_hint = model if connected else ""
        if connected:
            self.status_badge.setText(f"● LLM 在线{f' · {model}' if model else ''}")
            self.status_badge.setStyleSheet("color: #10b981; font-size: 12px; font-weight: 600;")
        else:
            self.status_badge.setText("● 本地降级")
            self.status_badge.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600;")

    def _restore_status_badge(self):
        if getattr(self, "_llm_connected", False):
            self.set_llm_connected(True, getattr(self, "_llm_model_hint", ""))
        else:
            self.set_llm_connected(False)

    def _render_all_messages(self):
        """根据当前主题重新渲染全部对话历史"""
        self.chat_display.clear()
        is_light = getattr(self, "_is_light_theme", False)
        bg = "#f1f5f9" if is_light else "#1e293b"
        text_col = "#0f172a" if is_light else "#e2e8f0"
        border = "#cbd5e1" if is_light else "#334155"
        user_bg = "#0284c7" if is_light else "#1e3a8a"
        user_text = "#ffffff"

        html_blocks = []
        for role, msg in self._message_history:
            if role == "user":
                html = f"""
                <div style='margin-bottom: 12px; text-align: right;'>
                    <div style='display: inline-block; max-width: 85%; background-color: {user_bg};
                                color: {user_text}; padding: 8px 12px; border-radius: 12px 12px 2px 12px;
                                text-align: left; font-size: 13px; line-height: 1.5;'>
                        <b style='color: #e2e8f0; font-size: 11px;'>您:</b><br>{msg}
                    </div>
                </div>
                """
            else:
                is_streaming = (role == "maid_stream")
                md_html = markdown.markdown(
                    msg,
                    extensions=['fenced_code', 'tables']
                )
                stream_cursor = " <span style='color: #38bdf8;'>▋</span>" if is_streaming else ""
                html = f"""
                <div style='margin-bottom: 12px; text-align: left;'>
                    <div style='display: inline-block; max-width: 90%; background-color: {bg};
                                color: {text_col}; border: 1px solid {border}; padding: 10px 14px; border-radius: 12px 12px 12px 2px;
                                font-size: 13px; line-height: 1.6;'>
                        <span style='color: #0284c7; font-weight: 700; font-size: 11px;'>ChessMaid:</span><br>{md_html}{stream_cursor}
                    </div>
                </div>
                """
            html_blocks.append(html)

        self.chat_display.setHtml("".join(html_blocks))
        sb = self.chat_display.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def append_user_message(self, text: str):
        self._message_history.append(("user", text))
        self._render_all_messages()

    def append_maid_chunk(self, chunk: str):
        """流式追加女仆消息片段"""
        if not self._message_history or self._message_history[-1][0] != "maid_stream":
            self._message_history.append(("maid_stream", chunk))
        else:
            prev = self._message_history[-1][1]
            self._message_history[-1] = ("maid_stream", prev + chunk)
        self._render_all_messages()

    def finalize_maid_stream(self, final_text: str):
        """结束流式输出，转为正式 maid 消息"""
        if self._message_history and self._message_history[-1][0] == "maid_stream":
            self._message_history.pop()
        self.append_maid_message(final_text)

    def append_maid_message(self, markdown_text: str):
        self._message_history.append(("maid", markdown_text))
        self._render_all_messages()

    def apply_theme(self, is_light: bool):
        """动态切换对话面板主题并重绘对话历史"""
        self._is_light_theme = is_light
        if is_light:
            self.title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #0f172a;")
            self.chat_display.setStyleSheet("""
                QTextBrowser {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 8px;
                    padding: 10px;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
                    font-size: 13px;
                }
            """)
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 7px 12px;
                    font-size: 13px;
                }
                QLineEdit:focus {
                    border: 1px solid #0284c7;
                }
            """)
            self.ask_llm_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 13px;
                    font-weight: 600;
                }
                QPushButton:hover { background-color: #0369a1; }
                QPushButton:pressed { background-color: #075985; }
                QPushButton:disabled { background-color: #e2e8f0; color: #94a3b8; }
            """)
            self.send_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 13px;
                    font-weight: 600;
                }
                QPushButton:hover { background-color: #0369a1; }
                QPushButton:pressed { background-color: #075985; }
                QPushButton:disabled { background-color: #e2e8f0; color: #94a3b8; }
            """)
        else:
            self.title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc;")
            self.chat_display.setStyleSheet("""
                QTextBrowser {
                    background-color: #0b0f19;
                    color: #e2e8f0;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                    padding: 10px;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
                    font-size: 13px;
                }
            """)
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: #111827;
                    color: #f8fafc;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 7px 12px;
                    font-size: 13px;
                }
                QLineEdit:focus {
                    border: 1px solid #38bdf8;
                }
            """)
            self.ask_llm_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 13px;
                    font-weight: 600;
                }
                QPushButton:hover { background-color: #0369a1; }
                QPushButton:pressed { background-color: #075985; }
                QPushButton:disabled { background-color: #1e293b; color: #64748b; }
            """)
            self.send_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 13px;
                    font-weight: 600;
                }
                QPushButton:hover { background-color: #1d4ed8; }
                QPushButton:pressed { background-color: #1e40af; }
                QPushButton:disabled { background-color: #1e293b; color: #64748b; }
            """)
        self._render_all_messages()

    def send_message(self, text: str):
        text = text.strip()
        if text:
            self.append_user_message(text)
            self.message_sent.emit(text)

    def _send_message(self):
        text = self.input_field.text().strip()
        if text:
            self.input_field.clear()
            self.send_message(text)
