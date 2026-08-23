"""
LLMConfigDialog 单元测试 (GUI 冒烟测试)
- 使用 QT_QPA_PLATFORM=offscreen 运行
- 验证 API Key 显隐切换
- 验证 get_config 返回格式 (包含 reasoning_effort 与 stream)
"""
import os
import unittest

# 必须在导入 PySide6 之前设置
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit
from src.gui.llm_config_dialog import LLMConfigDialog


class TestLLMConfigDialog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if QApplication.instance() is None:
            cls._app = QApplication([])
        else:
            cls._app = QApplication.instance()

    def setUp(self):
        self.dialog = LLMConfigDialog(current_config=None)

    def tearDown(self):
        self.dialog.close()

    # ---------- 初始化 / 预填 ----------

    def test_default_prefill_empty(self):
        dlg = LLMConfigDialog(current_config=None)
        self.assertEqual(dlg.base_input.text(), "")
        self.assertEqual(dlg.key_input.text(), "")
        self.assertEqual(dlg.model_input.text(), "")
        self.assertEqual(dlg.reasoning_combo.currentData(), "auto")
        self.assertFalse(dlg.chk_stream.isChecked())
        dlg.close()

    def test_current_config_prefilled(self):
        cfg = {
            "api_base": "https://custom.api.com",
            "api_key": "sk-custom-123",
            "model": "my-model-v1",
            "reasoning_effort": "high",
            "stream": True,
        }
        dlg = LLMConfigDialog(current_config=cfg)
        self.assertEqual(dlg.base_input.text(), "https://custom.api.com")
        self.assertEqual(dlg.key_input.text(), "sk-custom-123")
        self.assertEqual(dlg.model_input.text(), "my-model-v1")
        self.assertEqual(dlg.reasoning_combo.currentData(), "high")
        self.assertTrue(dlg.chk_stream.isChecked())
        dlg.close()

    # ---------- Key 显隐切换 ----------

    def test_key_starts_hidden(self):
        self.assertEqual(
            self.dialog.key_input.echoMode(),
            QLineEdit.Password,
        )

    def test_toggle_key_visibility(self):
        self.dialog._toggle_key_visibility(True)
        self.assertEqual(self.dialog.key_input.echoMode(), QLineEdit.Normal)
        self.dialog._toggle_key_visibility(False)
        self.assertEqual(self.dialog.key_input.echoMode(), QLineEdit.Password)

    # ---------- get_config ----------

    def test_get_config_returns_dict(self):
        self.dialog.base_input.setText("  https://x.com  ")
        self.dialog.key_input.setText("  sk-abc  ")
        self.dialog.model_input.setText("  my-model  ")
        self.dialog.reasoning_combo.setCurrentIndex(2)  # medium
        self.dialog.chk_stream.setChecked(True)
        cfg = self.dialog.get_config()
        self.assertIsInstance(cfg, dict)
        self.assertEqual(cfg["api_base"], "https://x.com")
        self.assertEqual(cfg["api_key"], "sk-abc")
        self.assertEqual(cfg["model"], "my-model")
        self.assertEqual(cfg["reasoning_effort"], "medium")
        self.assertTrue(cfg["stream"])

    def test_get_config_empty_fields(self):
        cfg = self.dialog.get_config()
        self.assertEqual(cfg["api_base"], "")
        self.assertEqual(cfg["api_key"], "")
        self.assertEqual(cfg["model"], "")
        self.assertEqual(cfg["reasoning_effort"], "auto")
        self.assertFalse(cfg["stream"])


if __name__ == "__main__":
    unittest.main()
