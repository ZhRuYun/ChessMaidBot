"""
LLM 配置对话框 (模块1 - GUI)
让用户在界面中填入 API Key / Base URL / 模型名称 / 思考档位 / 流式输出, 无需依赖环境变量

设计原则 (遵循 AGENTS.md):
  - 纯 GUI 组件, 只负责收集输入并通过信号返回配置字典
  - 不直接操作 LLMAgent 或任何业务逻辑 (解耦)
  - 预填当前 LLMAgent 的配置, 便于增量修改
"""
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QLabel, QCheckBox, QComboBox
)


class LLMConfigDialog(QDialog):
    """LLM 连接配置对话框

    通过 get_config() 静态方法弹出模态对话框, 返回用户填写的配置字典;
    用户取消时返回 None。
    """

    def __init__(self, current_config: Optional[dict] = None, parent=None):
        """
        Args:
            current_config: 当前 LLMAgent 的配置, 用于预填表单
                {
                    "api_base": str,
                    "api_key": str,
                    "model": str,
                    "reasoning_effort": str,
                    "stream": bool,
                }
        """
        super().__init__(parent)
        self.setWindowTitle("AI 女仆连接配置")
        self.setMinimumWidth(480)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0f19;
                color: #f1f5f9;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
            QLineEdit[echoMode="2"] {
                font-family: Consolas, "Courier New", monospace;
            }
            QComboBox {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #475569;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: #f8fafc;
                selection-background-color: #3b82f6;
                border: 1px solid #334155;
                padding: 4px;
            }
        """)

        current_config = current_config or {}
        self._build_ui(current_config)

    # ---------- UI 构建 ----------

    def _build_ui(self, current: dict):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(14)

        # 标题说明
        title = QLabel("⚙️ AI 女仆连接配置 (OpenAI 兼容)")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #38bdf8;")
        layout.addWidget(title)

        hint = QLabel(
            "填写下方信息后, ChessMaid 即可接入真实大语言模型进行棋艺教学。\n"
            "支持 OpenAI 标准思考档位 (reasoning_effort) 与流式输出 (Stream)。\n"
            "留空 API Key 则自动使用本地降级回复。"
        )
        hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 表单字段
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(form.alignment())

        # API Base URL
        self.base_input = QLineEdit(current.get("api_base", ""))
        self.base_input.setPlaceholderText("例如: https://api.deepseek.com 或 https://api.openai.com")
        form.addRow("API 基地址 (Base URL):", self.base_input)

        # API Key (密码模式, 遮罩显示)
        self.key_input = QLineEdit(current.get("api_key", ""))
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("sk-... (留空则使用本地降级回复)")
        form.addRow("API Key (密钥):", self.key_input)

        # 显示/隐藏密钥切换
        self.chk_show_key = QCheckBox("显示密钥明文")
        self.chk_show_key.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.chk_show_key.toggled.connect(self._toggle_key_visibility)
        form.addRow("", self.chk_show_key)

        # 模型名称
        self.model_input = QLineEdit(current.get("model", ""))
        self.model_input.setPlaceholderText("例如: deepseek-chat, gpt-4o, deepseek-reasoner")
        form.addRow("模型名称 (Model):", self.model_input)

        # 思考档位 (reasoning_effort)
        self.reasoning_combo = QComboBox()
        self.reasoning_combo.addItem("自动 / 不设 (auto/default)", "auto")
        self.reasoning_combo.addItem("低 (low)", "low")
        self.reasoning_combo.addItem("中 (medium)", "medium")
        self.reasoning_combo.addItem("高 (high)", "high")
        self.reasoning_combo.addItem("关闭思考 (none)", "none")

        current_effort = str(current.get("reasoning_effort", "auto")).lower()
        effort_index = 0
        for i in range(self.reasoning_combo.count()):
            if self.reasoning_combo.itemData(i) == current_effort:
                effort_index = i
                break
        self.reasoning_combo.setCurrentIndex(effort_index)
        form.addRow("思考档位 (Reasoning):", self.reasoning_combo)

        # 流式输出 (stream)
        self.chk_stream = QCheckBox("启用流式响应传输 (Stream)")
        self.chk_stream.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        self.chk_stream.setChecked(bool(current.get("stream", False)))
        form.addRow("流式输出 (Stream):", self.chk_stream)

        layout.addLayout(form)

        # 按钮组
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self
        )
        buttons.button(QDialogButtonBox.Ok).setText("保存并应用")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        for role_text in [buttons.button(QDialogButtonBox.Ok),
                          buttons.button(QDialogButtonBox.Cancel)]:
            role_text.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    padding: 7px 18px;
                    font-size: 13px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #3b82f6;
                }
            """)
        buttons.button(QDialogButtonBox.Cancel).setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #282f3e;
                color: #ffffff;
            }
        """)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ---------- 辅助方法 ----------

    def _toggle_key_visibility(self, checked: bool):
        """切换 API Key 明文/密文显示"""
        self.key_input.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)

    def get_config(self) -> dict:
        """返回用户填写的配置字典

        Returns:
            {
                "api_base": str,
                "api_key": str,
                "model": str,
                "reasoning_effort": str,
                "stream": bool,
            }
        """
        return {
            "api_base": self.base_input.text().strip(),
            "api_key": self.key_input.text().strip(),
            "model": self.model_input.text().strip(),
            "reasoning_effort": self.reasoning_combo.currentData(),
            "stream": self.chk_stream.isChecked(),
        }

    @staticmethod
    def get_config_dialog(
        current_config: Optional[dict] = None,
        parent=None
    ) -> Optional[dict]:
        """静态便捷方法: 弹出模态对话框, 返回配置字典或 None

        Args:
            current_config: 预填配置 (含 api_base/api_key/model/reasoning_effort/stream)
            parent: 父窗口

        Returns:
            用户确认 -> {"api_base":..., "api_key":..., "model":..., "reasoning_effort":..., "stream":...}
            用户取消 -> None
        """
        dialog = LLMConfigDialog(current_config=current_config, parent=parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_config()
        return None
