"""
LLM 女仆互动对话面板 (模块1 - GUI)
- 教学开关直接读写调度层的 TeachingTriggers 配置对象
- 快捷提问与手动输入共用同一条消息链路 (均显示用户气泡)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QLineEdit, QPushButton, QLabel, QGroupBox, QCheckBox, QFrame
)
from PySide6.QtCore import Signal
import markdown

from ..controller.teaching_triggers import TeachingTriggers

class ChatPanel(QWidget):
    message_sent = Signal(str)
    teaching_triggers_changed = Signal(object)

    QUICK_QUESTIONS = [
        ("💡 寻求建议", "女仆，请问我现在该注意什么？有推荐的下法吗？"),
        ("🔍 解释这步棋", "请为我分析并讲解刚刚这步棋的战术意图。"),
        ("⚖️ 评估当前局面", "请帮我综合评估一下双方现在的优劣势。"),
    ]

    def __init__(self, triggers: TeachingTriggers, parent=None):
        super().__init__(parent)
        self.triggers = triggers

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 1. 顶部女仆状态标头
        header_layout = QHBoxLayout()
        self.avatar_label = QLabel("♟️")
        self.avatar_label.setStyleSheet("font-size: 22px;")

        self.title_label = QLabel("ChessMaid 教学助手")
        self.title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #f0f0f0;")

        self.status_badge = QLabel("● 在线")
        self.status_badge.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold;")

        header_layout.addWidget(self.avatar_label)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_badge)
        layout.addLayout(header_layout)

        # 2. 教学触发器控制组 (1个总开关 + 4个细分开关)
        teaching_box = QGroupBox("🤖 女仆教学触发配置")
        teaching_box.setStyleSheet("""
            QGroupBox {
                color: #64b5f6;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #3d4a5d;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QCheckBox {
                color: #dcdcdc;
                font-size: 12px;
            }
            QCheckBox:disabled {
                color: #666677;
            }
        """)
        t_layout = QVBoxLayout(teaching_box)
        t_layout.setSpacing(4)
        t_layout.setContentsMargins(8, 6, 8, 6)

        # 总开关 (Master Switch)
        self.chk_master = QCheckBox("【总开关】开启女仆教学支持")
        self.chk_master.setChecked(self.triggers.master_enabled)
        self.chk_master.setStyleSheet("color: #4fc3f7; font-weight: bold;")
        self.chk_master.toggled.connect(self._on_master_toggled)
        t_layout.addWidget(self.chk_master)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #333344;")
        t_layout.addWidget(line)

        # 4个细分触发开关
        sub_layout = QVBoxLayout()
        sub_layout.setContentsMargins(15, 0, 0, 0)
        sub_layout.setSpacing(3)

        self.chk_eval_pos = QCheckBox("1. 当下局面评估")
        self.chk_suggest_moves = QCheckBox("2. 建议着法评估")
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

        # 3. 消息展示区 (默认完全空白)
        self.chat_display = QTextBrowser(self)
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setStyleSheet("""
            QTextBrowser {
                background-color: #1a1a24;
                color: #e6e6e6;
                border: 1px solid #333344;
                border-radius: 8px;
                padding: 10px;
                font-family: "Segoe UI", sans-serif;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.chat_display)

        # 4. 快捷提问按钮条
        quick_btn_layout = QHBoxLayout()
        quick_btn_layout.setSpacing(6)
        for label, question in self.QUICK_QUESTIONS:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2b2b38;
                    color: #d1d5db;
                    border: 1px solid #3f3f52;
                    border-radius: 6px;
                    padding: 5px 8px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #3d3d52;
                    color: #ffffff;
                }
            """)
            btn.clicked.connect(lambda _, q=question: self.send_message(q))
            quick_btn_layout.addWidget(btn)

        layout.addLayout(quick_btn_layout)

        # 5. 底部输入框与发送按钮
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("向女仆请教国际象棋问题...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #242430;
                color: #ffffff;
                border: 1px solid #444458;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #3d84b8;
            }
        """)
        self.input_field.returnPressed.connect(self._send_message)

        self.send_btn = QPushButton("发送", self)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d84b8;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #4a94cb;
            }
        """)
        self.send_btn.clicked.connect(self._send_message)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        layout.addLayout(input_layout)

    def _on_master_toggled(self, checked: bool):
        for chk, _attr in self._sub_checks:
            chk.setEnabled(checked)
        self._update_triggers()

    def _update_triggers(self):
        self.triggers.master_enabled = self.chk_master.isChecked()
        for chk, attr in self._sub_checks:
            setattr(self.triggers, attr, chk.isChecked())
        self.teaching_triggers_changed.emit(self.triggers)

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
            <div style='display: inline-block; background-color: #34495e; color: #ffffff; padding: 8px 12px; border-radius: 12px 12px 2px 12px; max-width: 85%; text-align: left;'>
                <b>您:</b><br>{text}
            </div>
        </div>
        """
        self.chat_display.append(html)

    def append_maid_message(self, text: str):
        md_html = markdown.markdown(text, extensions=['extra'])
        html = f"""
        <div style='margin-bottom: 12px; text-align: left;'>
            <div style='display: inline-block; background-color: #242b35; color: #e1e7ec; padding: 8px 12px; border-radius: 12px 12px 12px 2px; border-left: 3px solid #64b5f6; max-width: 90%;'>
                <span style='color: #64b5f6; font-weight: bold;'>♟️ ChessMaid:</span><br>{md_html}
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
