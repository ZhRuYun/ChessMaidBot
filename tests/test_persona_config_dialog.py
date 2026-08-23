"""
PersonaConfigDialog 单元测试 (GUI 冒烟测试)
- 使用 QT_QPA_PLATFORM=offscreen 运行
- 验证预设下拉框与模板载入
- 验证恢复默认 / 清空
- 验证字符计数实时更新
- 验证接受时非空校验
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from src.gui.persona_config_dialog import PersonaConfigDialog, PERSONA_PRESETS


class TestPersonaConfigDialog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if QApplication.instance() is None:
            cls._app = QApplication([])
        else:
            cls._app = QApplication.instance()

    def setUp(self):
        self.dialog = PersonaConfigDialog(current_persona="")

    def tearDown(self):
        self.dialog.close()

    # ---------- 初始化 ----------

    def test_preset_combo_matches_presets(self):
        self.assertEqual(
            self.dialog.preset_combo.count(),
            len(PERSONA_PRESETS),
        )

    def test_current_persona_prefilled(self):
        persona = "我是自定义的人设文本。"
        dlg = PersonaConfigDialog(current_persona=persona)
        self.assertEqual(dlg.editor.toPlainText(), persona)
        dlg.close()

    def test_character_count_initial_zero(self):
        dlg = PersonaConfigDialog(current_persona="")
        self.assertEqual(dlg.count_label.text(), "0 字符")
        dlg.close()

    # ---------- 字符计数 ----------

    def test_character_count_updates(self):
        self.dialog.editor.setPlainText("hello")
        self.assertEqual(self.dialog.count_label.text(), "5 字符")
        self.dialog.editor.setPlainText("你好世界")
        self.assertEqual(self.dialog.count_label.text(), "4 字符")

    # ---------- 恢复默认 ----------

    def test_reset_default(self):
        self.dialog.editor.setPlainText("乱七八糟的内容")
        self.dialog._on_reset_default()
        expected = PERSONA_PRESETS[0][2]
        self.assertEqual(self.dialog.editor.toPlainText(), expected)
        self.assertEqual(self.dialog.preset_combo.currentIndex(), 0)

    # ---------- 清空 ----------

    def test_clear_editor(self):
        self.dialog.editor.setPlainText("要被清空的内容")
        self.dialog._on_clear()
        self.assertEqual(self.dialog.editor.toPlainText(), "")
        # 注: hasFocus() 在 offscreen 平台下不可靠, 跳过焦点断言

    # ---------- 预设描述切换 ----------

    def test_preset_desc_changes_on_combo(self):
        if len(PERSONA_PRESETS) >= 2:
            self.dialog.preset_combo.setCurrentIndex(1)
            expected_desc = PERSONA_PRESETS[1][1]
            self.assertIn(expected_desc, self.dialog.preset_desc_label.text())

    # ---------- 应用预设 ----------

    def test_apply_preset_overwrites_empty(self):
        # 编辑区为空, 直接载入
        self.dialog.editor.setPlainText("")
        self.dialog.preset_combo.setCurrentIndex(0)
        self.dialog._on_apply_preset()
        expected = PERSONA_PRESETS[0][2]
        self.assertEqual(self.dialog.editor.toPlainText(), expected)

    def test_apply_preset_on_second_template(self):
        if len(PERSONA_PRESETS) >= 2:
            self.dialog.editor.setPlainText("")
            self.dialog.preset_combo.setCurrentIndex(1)
            self.dialog._on_apply_preset()
            self.assertEqual(self.dialog.editor.toPlainText(), PERSONA_PRESETS[1][2])

    # ---------- 接受 / 取消校验 ----------

    def test_accept_empty_shows_warning(self):
        """空人设时点击保存应弹警告且不 accept"""
        self.dialog.editor.setPlainText("   ")
        # 用 patch 避免弹窗阻塞测试
        warned = []
        original = QMessageBox.warning
        def fake_warning(*args, **kwargs):
            warned.append(True)
            return QMessageBox.Ok
        QMessageBox.warning = fake_warning
        try:
            # _on_accept 在内容为空时, 不会调用 self.accept()
            self.dialog._on_accept()
            # 验证弹窗出现
            self.assertTrue(len(warned) > 0)
        finally:
            QMessageBox.warning = original

    def test_accept_non_empty(self):
        """非空人设应正常 accept"""
        self.dialog.editor.setPlainText("有效的人设文本")
        # 直接调用, 应正常执行 (不弹警告)
        warned = []
        original = QMessageBox.warning
        def fake_warning(*args, **kwargs):
            warned.append(True)
            return QMessageBox.Ok
        QMessageBox.warning = fake_warning
        try:
            # 捕获 accept 行为: result() 在 accept 后是 QDialog.Accepted (1)
            self.dialog._on_accept()
            self.assertEqual(self.dialog.result(), 1)
            self.assertEqual(len(warned), 0)
        finally:
            QMessageBox.warning = original

    # ---------- get_persona ----------

    def test_get_persona_strips_whitespace(self):
        self.dialog.editor.setPlainText("  人设内容  \n\n  ")
        self.assertEqual(self.dialog.get_persona(), "人设内容")


if __name__ == "__main__":
    unittest.main()
