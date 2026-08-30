import os
import unittest
from PySide6.QtWidgets import QApplication
from src.core.board_state import BoardState
from src.controller.teaching_triggers import TeachingTriggers
from src.gui.chess_board import ChessBoardWidget
from src.gui.control_bar import ControlBar
from src.gui.move_history_panel import MoveHistoryPanel
from src.gui.chat_panel import ChatPanel

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


if __name__ == "__main__":
    unittest.main()
