"""
女仆人设 Prompt 配置对话框 (模块1 - GUI)
让用户在界面中自定义 AI 女仆的人设提示词 (Persona Prompt)

设计原则 (遵循 AGENTS.md):
  - 纯 GUI 组件, 只负责收集输入并通过静态方法返回字符串
  - 不直接操作 LLMAgent 或任何业务逻辑 (解耦)
  - 预填当前人设, 提供多个预设模板供用户快速选择
  - 支持一键恢复默认人设
"""
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPlainTextEdit,
    QDialogButtonBox, QFrame, QPushButton, QHBoxLayout,
    QComboBox, QMessageBox
)


# 预设人设模板库 (只保留默认 Maid 模板，用户可新建并自定义自己的模板)
# 每项格式: (模板名称, 模板描述, 模板正文)
PERSONA_PRESETS = [
    (
        "ChessMaid 默认女仆",
        "温柔细致、富有战术洞察与陪伴学习的 AI 棋艺女仆",
        "你是一位精通国际象棋且温柔细致的AI棋艺女仆助理【ChessMaid】。"
        "你的核心职责是陪伴主人对弈并提供富有洞察力的战术指导与大局观教学。"
        "在解答与指导时：\n"
        "1. 语言亲切得体、精炼精准，优先剖析空间、子力协调、王安全与关键格控制等核心棋理。\n"
        "2. 指出走法意图与战术威胁，给出清晰可行的后续计划。\n"
        "3. 严禁废话与套话，严禁输出任何emoji表情符号。"
    ),
]


class PersonaConfigDialog(QDialog):
    """女仆人设 Prompt 配置对话框"""

    def __init__(self, current_persona: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎭 自定义女仆人设 (Persona)")
        self.setMinimumWidth(540)
        self.setMinimumHeight(460)
        
        # 兼容父窗口浅色主题
        is_light = False
        if parent and hasattr(parent, "control_bar") and hasattr(parent.control_bar, "theme_combo"):
            is_light = (parent.control_bar.theme_combo.currentText() == "浅色")

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
                QPlainTextEdit {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 13px;
                }
                QComboBox {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 6px 10px;
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
                QPlainTextEdit {
                    background-color: #1e293b;
                    color: #f8fafc;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 13px;
                    line-height: 1.6;
                    selection-background-color: #2563eb;
                }
                QPlainTextEdit:focus {
                    border: 1px solid #38bdf8;
                }
                QComboBox {
                    background-color: #1e293b;
                    color: #f1f5f9;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 6px 10px;
                }
                QComboBox QAbstractItemView {
                    background-color: #1e293b;
                    color: #f1f5f9;
                    selection-background-color: #3b82f6;
                    border: 1px solid #334155;
                }
            """)

        self._build_ui(current_persona or "")

    # ---------- UI 构建 ----------

    def _build_ui(self, current: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        # 标题
        title = QLabel("🎭 自定义女仆人设 (Persona Prompt)")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #a78bfa;")
        layout.addWidget(title)

        hint = QLabel(
            "人设 Prompt 决定 AI 女仆的性格、语气与分析风格。\n"
            "可从下方模板选择一个起点, 也可在编辑框中自由修改后保存。"
        )
        hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 预设模板下拉选择
        preset_row = QHBoxLayout()
        preset_label = QLabel("预设模板:")
        preset_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600;")
        preset_row.addWidget(preset_label)

        self.preset_combo = QComboBox()
        for name, _desc, _text in PERSONA_PRESETS:
            self.preset_combo.addItem(name)
        self.preset_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                color: #a78bfa;
                border: 1px solid #6d28d9;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: 600;
            }
        """)
        preset_row.addWidget(self.preset_combo, 1)

        # 应用预设按钮
        btn_apply_preset = QPushButton("载入模板")
        btn_apply_preset.setStyleSheet("""
            QPushButton {
                background-color: #6d28d9;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #7c3aed;
            }
        """)
        btn_apply_preset.clicked.connect(self._on_apply_preset)
        preset_row.addWidget(btn_apply_preset)
        layout.addLayout(preset_row)

        # 模板描述提示
        self.preset_desc_label = QLabel("")
        self.preset_desc_label.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic;")
        self.preset_desc_label.setWordWrap(True)
        layout.addWidget(self.preset_desc_label)
        # 初始化描述为第一个模板
        if PERSONA_PRESETS:
            self.preset_desc_label.setText(f"模板说明: {PERSONA_PRESETS[0][1]}")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)

        # 分割线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #1e293b;")
        layout.addWidget(sep)

        # 人设编辑区
        editor_label = QLabel("人设 Prompt 编辑区:")
        editor_label.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: 600;")
        layout.addWidget(editor_label)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "在此编辑 AI 女仆的人设 Prompt...\n\n"
            "示例:\n"
            "你是一位精通国际象棋且温柔细致的AI棋艺女仆助理..."
        )
        self.editor.setPlainText(current)
        layout.addWidget(self.editor, 1)

        # 底部辅助按钮: 恢复默认 / 清空
        aux_row = QHBoxLayout()
        btn_reset_default = QPushButton("↩️ 恢复默认人设")
        btn_reset_default.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #282f3e;
                color: #f1f5f9;
            }
        """)
        btn_reset_default.clicked.connect(self._on_reset_default)
        aux_row.addWidget(btn_reset_default)

        btn_clear = QPushButton("🗑 清空")
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #282f3e;
                color: #f1f5f9;
            }
        """)
        btn_clear.clicked.connect(self._on_clear)
        aux_row.addWidget(btn_clear)

        aux_row.addStretch()

        # 字符计数显示
        self.count_label = QLabel("0 字符")
        self.count_label.setStyleSheet("color: #64748b; font-size: 11px;")
        aux_row.addWidget(self.count_label)
        layout.addLayout(aux_row)
        self.editor.textChanged.connect(self._update_count)

        # 按钮组
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self
        )
        buttons.button(QDialogButtonBox.Ok).setText("保存并应用")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.Ok).setStyleSheet("""
            QPushButton {
                background-color: #6d28d9;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #7c3aed;
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
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 初始化字符计数
        self._update_count()

    # ---------- 槽函数 ----------

    def _on_preset_selected(self, index: int):
        """下拉框选择变化时, 更新模板说明"""
        if 0 <= index < len(PERSONA_PRESETS):
            _name, desc, _text = PERSONA_PRESETS[index]
            self.preset_desc_label.setText(f"模板说明: {desc}")

    def _on_apply_preset(self):
        """载入选中的预设模板到编辑区 (会覆盖现有内容, 但有确认提示)"""
        idx = self.preset_combo.currentIndex()
        if not (0 <= idx < len(PERSONA_PRESETS)):
            return
        current_text = self.editor.toPlainText().strip()
        if current_text:
            # 已有内容, 询问是否覆盖
            reply = QMessageBox.question(
                self, "覆盖现有人设?",
                "编辑区已有内容, 载入模板将覆盖当前内容。是否继续?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        _name, _desc, text = PERSONA_PRESETS[idx]
        self.editor.setPlainText(text)
        self.editor.setFocus()

    def _on_reset_default(self):
        """恢复为默认人设 (ChessMaid 默认女仆)"""
        if PERSONA_PRESETS:
            self.editor.setPlainText(PERSONA_PRESETS[0][2])
            self.preset_combo.setCurrentIndex(0)

    def _on_clear(self):
        """清空编辑区"""
        self.editor.clear()
        self.editor.setFocus()

    def _on_accept(self):
        """确认保存时校验非空"""
        text = self.editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(
                self, "人设不能为空",
                "人设 Prompt 不能为空, 请输入内容或选择预设模板。"
            )
            return
        self.accept()

    def _update_count(self):
        """实时更新字符计数"""
        text = self.editor.toPlainText()
        self.count_label.setText(f"{len(text)} 字符")

    # ---------- 公开接口 ----------

    def get_persona(self) -> str:
        """返回用户编辑后的人设字符串"""
        return self.editor.toPlainText().strip()

    @staticmethod
    def get_persona_dialog(
        current_persona: str = "",
        parent=None
    ) -> Optional[str]:
        """静态便捷方法: 弹出模态对话框, 返回人设字符串或 None

        Args:
            current_persona: 预填的人设 Prompt
            parent: 父窗口

        Returns:
            用户确认 -> 人设字符串 (非空)
            用户取消 -> None
        """
        dialog = PersonaConfigDialog(current_persona=current_persona, parent=parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_persona()
        return None
