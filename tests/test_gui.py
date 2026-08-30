import os
import unittest
from PySide6.QtWidgets import QApplication
from src.core.board_state import BoardState
from src.controller.teaching_triggers import TeachingTriggers
from src.gui.chess_board import ChessBoardWidget
from src.gui.control_bar import ControlBar
from src.gui.move_history_panel import MoveHistoryPanel
from src.gui.chat_panel import ChatPanel
from src.gui.llm_config_dialog import LLMConfigDialog

# Ensure QApp exists in offscreen mode
os.environ["QT_QPA_PLATFORM"] = "offscreen"
app = QApplication.instance() or QApplication([])


class TestGUI(unittest.TestCase):
    def test_gui_components_creation(self):
        state = BoardState()
        board = ChessBoardWidget(board_state=state)
        self.assertIsNotNone(board)

        bar = ControlBar()
        self.assertIsNotNone(bar)

        history = MoveHistoryPanel()
        self.assertIsNotNone(history)

        chat = ChatPanel()
        self.assertIsNotNone(chat)

    def test_llm_config_dialog_creation(self):
        """回归测试: AI 设置对话框在无父窗口时必须可正常构建 (曾因 is_light 未定义而崩溃)"""
        dialog = LLMConfigDialog(
            current_config={"api_base": "https://api.deepseek.com", "api_key": ""},
            current_triggers=TeachingTriggers(),
            current_persona="test persona",
        )
        self.assertTrue(dialog._is_light is False)
        self.assertEqual(dialog.get_persona(), "test persona")
        config = dialog.get_config()
        self.assertEqual(config["api_base"], "https://api.deepseek.com")
        self.assertFalse(config["stream"])


if __name__ == "__main__":
    unittest.main()
