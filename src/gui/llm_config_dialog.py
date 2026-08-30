"""
LLM 配置对话框 (模块1 - GUI)
整合:
  1. API 连接配置 (API Key / Base URL / 模型名称 / 思考档位 / 流式输出)
  2. 教学触发器配置 (总开关 + 4 个子开关)
  3. 自定义 AI 人设 (预设模板 + 自定义编辑)
"""
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QLabel, QCheckBox, QComboBox,
    QTabWidget, QWidget, QPlainTextEdit, QPushButton, QHBoxLayout, QMessageBox
)

from .persona_config_dialog import PERSONA_PRESETS
from ..controller.teaching_triggers import TeachingTriggers
from ..config import DEFAULT_MAID_PERSONA
from ..agents.llm_agent import LLMAgent


class LLMConfigDialog(QDialog):
    """综合 AI 设置对话框"""

    def __init__(
        self,
        current_config: Optional[dict] = None,
        current_triggers: Optional[TeachingTriggers] = None,
        current_persona: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("AI 综合配置")
        self.setMinimumWidth(560)
        self.setMinimumHeight(520)

        is_light = False
        if parent and hasattr(parent, "control_bar") and hasattr(parent.control_bar, "theme_combo"):
            is_light = (parent.control_bar.theme_combo.currentText() == "浅色")
        # 保存到实例属性, 供 _build_ui 中的控件配色使用 (修复原先引用未定义变量的崩溃)
        self._is_light = is_light

        if is_light:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f8fafc;
                    color: #0f172a;
                }
                QLabel {
                    color: #334155;
                    font-size: 13px;
                }
                QTabWidget::pane {
                    border: 1px solid #cbd5e1;
                    background-color: #ffffff;
                    border-radius: 6px;
                }
                QTabBar::tab {
                    background-color: #e2e8f0;
                    color: #475569;
                    padding: 8px 16px;
                    font-size: 13px;
                    font-weight: 600;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #ffffff;
                    color: #0284c7;
                    border-bottom: 2px solid #0284c7;
                }
                QLineEdit, QPlainTextEdit {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-size: 13px;
                }
                QLineEdit:focus, QPlainTextEdit:focus {
                    border: 1px solid #0284c7;
                }
                QComboBox {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-size: 13px;
                }
                QCheckBox {
                    color: #334155;
                    font-size: 13px;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 4px;
                    border: 1px solid #94a3b8;
                    background-color: #ffffff;
                }
                QCheckBox::indicator:checked {
                    background-color: #0284c7;
                    border-color: #0284c7;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #0b0f19;
                    color: #f1f5f9;
                }
                QLabel {
                    color: #cbd5e1;
                    font-size: 13px;
                }
                QTabWidget::pane {
                    border: 1px solid #334155;
                    background-color: #0f172a;
                    border-radius: 6px;
                }
                QTabBar::tab {
                    background-color: #1e293b;
                    color: #94a3b8;
                    padding: 8px 16px;
                    font-size: 13px;
                    font-weight: 600;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #0f172a;
                    color: #38bdf8;
                    border-bottom: 2px solid #38bdf8;
                }
                QLineEdit, QPlainTextEdit {
                    background-color: #1e293b;
                    color: #f8fafc;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-size: 13px;
                }
                QLineEdit:focus, QPlainTextEdit:focus {
                    border: 1px solid #38bdf8;
                }
                QComboBox {
                    background-color: #1e293b;
                    color: #f8fafc;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-size: 13px;
                }
                QCheckBox {
                    color: #cbd5e1;
                    font-size: 13px;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 4px;
                    border: 1px solid #475569;
                    background-color: #1e293b;
                }
                QCheckBox::indicator:checked {
                    background-color: #38bdf8;
                    border-color: #38bdf8;
                }
            """)

        current_config = current_config or {}
        current_triggers = current_triggers or TeachingTriggers()
        current_persona = current_persona or DEFAULT_MAID_PERSONA

        self._build_ui(current_config, current_triggers, current_persona)

    def _build_ui(self, current: dict, triggers: TeachingTriggers, persona: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title = QLabel("AI 综合设置 (AI Settings)")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #38bdf8;")
        layout.addWidget(title)

        self.tabs = QTabWidget(self)

        # Tab 1: API 连接
        tab_api = QWidget()
        api_layout = QVBoxLayout(tab_api)
        form = QFormLayout()
        form.setSpacing(10)

        self.base_input = QLineEdit(current.get("api_base", ""))
        self.base_input.setPlaceholderText("例如: https://api.deepseek.com")
        form.addRow("API 基地址 (Base URL):", self.base_input)

        self.key_input = QLineEdit(current.get("api_key", ""))
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("sk-... (留空则使用本地降级模式)")
        form.addRow("API Key (密钥):", self.key_input)

        self.chk_show_key = QCheckBox("显示密钥明文")
        self.chk_show_key.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.chk_show_key.toggled.connect(self._toggle_key_visibility)
        form.addRow("", self.chk_show_key)

        self.model_input = QLineEdit(current.get("model", ""))
        self.model_input.setPlaceholderText("例如: deepseek-chat, gpt-4o")

        # 模型选择与拉取行
        model_row = QHBoxLayout()
        model_row.addWidget(self.model_input, stretch=1)
        self.btn_test_fetch = QPushButton("测试连接并拉取模型")
        # 按钮配色跟随主窗口当前主题 (浅色/深色)
        self.btn_test_fetch.setStyleSheet(
            "background-color: #0284c7; color: #ffffff; padding: 5px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;"
            if self._is_light else
            "background-color: #2563eb; color: #ffffff; padding: 5px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;"
        )
        self.btn_test_fetch.clicked.connect(self._on_test_fetch_models)
        model_row.addWidget(self.btn_test_fetch)

        # 远端拉取后的模型下拉选择
        self.remote_models_combo = QComboBox()
        self.remote_models_combo.setVisible(False)
        self.remote_models_combo.currentTextChanged.connect(self._on_remote_model_picked)
        model_row.addWidget(self.remote_models_combo)

        form.addRow("模型名称 (Model):", model_row)

        self.search_url_input = QLineEdit(current.get("search_api_url", ""))
        self.search_url_input.setPlaceholderText("可选: https://api.tavily.com/search (留空免key)")
        form.addRow("搜索接口 (Search URL):", self.search_url_input)

        self.search_key_input = QLineEdit(current.get("search_api_key", ""))
        self.search_key_input.setEchoMode(QLineEdit.Password)
        self.search_key_input.setPlaceholderText("可选: Search API Key (留空免key)")
        form.addRow("搜索密钥 (Search Key):", self.search_key_input)

        self.reasoning_combo = QComboBox()
        self.reasoning_combo.addItem("自动 / 默认 (auto)", "auto")
        self.reasoning_combo.addItem("低 (low)", "low")
        self.reasoning_combo.addItem("中 (medium)", "medium")
        self.reasoning_combo.addItem("高 (high)", "high")
        self.reasoning_combo.addItem("最大 (max)", "max")
        self.reasoning_combo.addItem("关闭思考 (none)", "none")
        current_effort = str(current.get("reasoning_effort", "auto")).lower()
        for i in range(self.reasoning_combo.count()):
            if self.reasoning_combo.itemData(i) == current_effort:
                self.reasoning_combo.setCurrentIndex(i)
                break
        form.addRow("思考档位 (Reasoning):", self.reasoning_combo)

        self.chk_stream = QCheckBox("启用流式响应传输 (Stream)")
        self.chk_stream.setChecked(bool(current.get("stream", False)))
        form.addRow("流式输出 (Stream):", self.chk_stream)

        self.chk_tool_records = QCheckBox("在对话中显示简短工具调用记录 (开发者选项)")
        self.chk_tool_records.setChecked(bool(current.get("show_tool_records", False)))
        form.addRow("调试记录:", self.chk_tool_records)

        api_layout.addLayout(form)
        api_layout.addStretch()
        self.tabs.addTab(tab_api, "API 连接配置")

        # Tab 2: 教学触发器
        tab_teaching = QWidget()
        teach_layout = QVBoxLayout(tab_teaching)
        teach_layout.setSpacing(12)

        self.chk_master = QCheckBox("启用自动教学总开关 (Master)")
        self.chk_master.setChecked(triggers.master_enabled)
        self.chk_master.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px;")

        self.chk_eval_pos = QCheckBox("局面评估开关: 自动解读子力平衡、王安全与中心控制")
        self.chk_eval_pos.setChecked(triggers.eval_current_position)

        self.chk_suggest_move = QCheckBox("走法建议开关: 推荐 1~3 步高质量候选思路与计划")
        self.chk_suggest_move.setChecked(triggers.suggest_moves)

        self.chk_eval_hist = QCheckBox("历史评估开关: 走法点评与失误漏洞预警")
        self.chk_eval_hist.setChecked(triggers.eval_history_moves)

        self.chk_summary = QCheckBox("终局复盘开关: 对局结束时自动进行复盘总结")
        self.chk_summary.setChecked(triggers.game_over_summary)

        teach_layout.addWidget(self.chk_master)
        teach_layout.addWidget(self.chk_eval_pos)
        teach_layout.addWidget(self.chk_suggest_move)
        teach_layout.addWidget(self.chk_eval_hist)
        teach_layout.addWidget(self.chk_summary)
        teach_layout.addStretch()
        self.tabs.addTab(tab_teaching, "教学触发器配置")

        # Tab 3: 自定义 AI 人设
        tab_persona = QWidget()
        persona_layout = QVBoxLayout(tab_persona)
        persona_layout.setSpacing(10)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("选择预设模板:"))
        self.persona_combo = QComboBox()
        for name, desc, _ in PERSONA_PRESETS:
            self.persona_combo.addItem(f"{name} ({desc})")
        preset_row.addWidget(self.persona_combo, stretch=1)
        self.persona_combo.currentIndexChanged.connect(self._on_preset_selected)
        persona_layout.addLayout(preset_row)

        self.persona_edit = QPlainTextEdit(persona)
        persona_layout.addWidget(self.persona_edit)

        p_btn_row = QHBoxLayout()
        btn_reset = QPushButton("恢复默认人设")
        btn_reset.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px;")
        btn_reset.clicked.connect(lambda: self.persona_edit.setPlainText(DEFAULT_MAID_PERSONA))
        p_btn_row.addWidget(btn_reset)
        p_btn_row.addStretch()
        persona_layout.addLayout(p_btn_row)

        self.tabs.addTab(tab_persona, "自定义 AI 人设")

        layout.addWidget(self.tabs)

        # 底部对话框按钮组
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.button(QDialogButtonBox.Ok).setText("保存并应用")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.Ok).setStyleSheet("background-color: #2563eb; color: #fff; padding: 6px 16px; font-weight: bold; border-radius: 4px;")
        buttons.button(QDialogButtonBox.Cancel).setStyleSheet("background-color: #334155; color: #fff; padding: 6px 16px; border-radius: 4px;")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _toggle_key_visibility(self, checked: bool):
        """切换 API Key 明文/密文显示"""
        self.key_input.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)

    def _on_test_fetch_models(self):
        """测试连接并拉取模型列表"""
        api_base = self.base_input.text().strip() or "https://api.deepseek.com"
        api_key = self.key_input.text().strip()

        self.btn_test_fetch.setEnabled(False)
        self.btn_test_fetch.setText("测试中...")
        try:
            models = LLMAgent.test_connection_and_fetch_models(api_base, api_key, timeout=8)
            if models:
                self.remote_models_combo.blockSignals(True)
                self.remote_models_combo.clear()
                self.remote_models_combo.addItem("-- 选择拉取到的模型 --")
                for m in models:
                    self.remote_models_combo.addItem(m)
                self.remote_models_combo.blockSignals(False)
                self.remote_models_combo.setVisible(True)
                QMessageBox.information(
                    self,
                    "连接成功",
                    f"成功连接至 API 接口！共获取到 {len(models)} 个模型。\n您可在右侧下拉框中直接选择，或继续手动输入。"
                )
            else:
                QMessageBox.information(
                    self,
                    "连接成功",
                    "成功连通 API 服务，但接口返回的模型列表为空。您可以直接在输入框填写模型名称。"
                )
        except Exception as e:
            QMessageBox.warning(
                self,
                "连接失败",
                f"未能连通 API 接口或拉取模型失败：\n\n{e}\n\n请检查 Base URL、API Key 或网络连接。"
            )
        finally:
            self.btn_test_fetch.setEnabled(True)
            self.btn_test_fetch.setText("测试连接并拉取模型")

    def _on_remote_model_picked(self, text: str):
        if text and not text.startswith("--"):
            self.model_input.setText(text)

    def _on_preset_selected(self, index: int):
        if 0 <= index < len(PERSONA_PRESETS):
            _, _, prompt = PERSONA_PRESETS[index]
            self.persona_edit.setPlainText(prompt)

    def get_config(self) -> dict:
        return {
            "api_base": self.base_input.text().strip(),
            "api_key": self.key_input.text().strip(),
            "model": self.model_input.text().strip(),
            "search_api_url": self.search_url_input.text().strip(),
            "search_api_key": self.search_key_input.text().strip(),
            "reasoning_effort": self.reasoning_combo.currentData(),
            "stream": self.chk_stream.isChecked(),
            "show_tool_records": self.chk_tool_records.isChecked(),
        }

    def get_triggers(self) -> TeachingTriggers:
        return TeachingTriggers(
            master_enabled=self.chk_master.isChecked(),
            eval_current_position=self.chk_eval_pos.isChecked(),
            suggest_moves=self.chk_suggest_move.isChecked(),
            eval_history_moves=self.chk_eval_hist.isChecked(),
            game_over_summary=self.chk_summary.isChecked(),
        )

    def get_persona(self) -> str:
        return self.persona_edit.toPlainText().strip() or DEFAULT_MAID_PERSONA

    @staticmethod
    def get_config_dialog(
        current_config: Optional[dict] = None,
        current_triggers: Optional[TeachingTriggers] = None,
        current_persona: Optional[str] = None,
        parent=None
    ):
        dialog = LLMConfigDialog(
            current_config=current_config,
            current_triggers=current_triggers,
            current_persona=current_persona,
            parent=parent
        )
        if dialog.exec() == QDialog.Accepted:
            return {
                "config": dialog.get_config(),
                "triggers": dialog.get_triggers(),
                "persona": dialog.get_persona(),
            }
        return None
