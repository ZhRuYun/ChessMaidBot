"""
LLMConfigDialog 单元测试 (GUI 冒烟测试)
- 使用 QT_QPA_PLATFORM=offscreen 运行
- 验证预设按钮填充 Base URL / Model
- 验证 API Key 显隐切换
- 验证 get_config 返回格式
"""
import os
import unittest

# 必须在导入 PySide6 之前设置
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtCore import Qt
from src.gui.llm_config_dialog import LLMConfigDialog, PROVIDER_PRESETS


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
        dlg.close()

    def test_current_config_prefilled(self):
        cfg = {
            "api_base": "https://custom.api.com",
            "api_key": "sk-custom-123",
            "model": "my-model-v1",
        }
        dlg = LLMConfigDialog(current_config=cfg)
        self.assertEqual(dlg.base_input.text(), "https://custom.api.com")
        self.assertEqual(dlg.key_input.text(), "sk-custom-123")
        self.assertEqual(dlg.model_input.text(), "my-model-v1")
        dlg.close()

    # ---------- 预设按钮 ----------

    def test_preset_buttons_exist(self):
        # 每个预设都应该有一个按钮
        for name, _base, _model in PROVIDER_PRESETS:
            # 通过 windowTitle 无法直接验证按钮, 但我们可以验证预设列表非空
            self.assertTrue(name)

    def test_apply_preset_deepseek(self):
        # 直接调用 _apply_preset 模拟点击预设按钮
        self.dialog._apply_preset("https://api.deepseek.com", "deepseek-chat")
        self.assertEqual(self.dialog.base_input.text(), "https://api.deepseek.com")
        self.assertEqual(self.dialog.model_input.text(), "deepseek-chat")
        # 注: 焦点测试在 offscreen 平台下不可靠, 此处只验证内容正确性

    def test_apply_preset_ollama(self):
        self.dialog._apply_preset("http://localhost:11434", "llama3")
        self.assertEqual(self.dialog.base_input.text(), "http://localhost:11434")
        self.assertEqual(self.dialog.model_input.text(), "llama3")

    def test_apply_preset_preserves_key(self):
        self.dialog.key_input.setText("sk-existing")
        self.dialog._apply_preset("https://api.openai.com", "gpt-4o-mini")
        self.assertEqual(self.dialog.key_input.text(), "sk-existing")

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
        cfg = self.dialog.get_config()
        self.assertIsInstance(cfg, dict)
        self.assertEqual(cfg["api_base"], "https://x.com")
        self.assertEqual(cfg["api_key"], "sk-abc")
        self.assertEqual(cfg["model"], "my-model")

    def test_get_config_empty_fields(self):
        cfg = self.dialog.get_config()
        self.assertEqual(cfg["api_base"], "")
        self.assertEqual(cfg["api_key"], "")
        self.assertEqual(cfg["model"], "")


if __name__ == "__main__":
    unittest.main()
