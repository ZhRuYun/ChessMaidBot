"""
GUI 离屏冒烟测试: 验证棋盘→调度层→各面板的完整信号链路
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import chess
from PySide6.QtWidgets import QApplication

from src.agents.echo_agent import EchoAgent
from src.config import DEFAULT_MAID_PERSONA
from src.controller.game_controller import GameController
from src.database.history_store import HistoryStore
from src.gui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])


class TestGuiSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        controller = GameController(history_store=HistoryStore(root=Path(self.tmp.name)))
        self.window = MainWindow(
            agent=EchoAgent(persona_prompt=DEFAULT_MAID_PERSONA),
            controller=controller,
        )
        self.window.show()

    def tearDown(self):
        self.window.close()
        self.tmp.cleanup()

    def test_full_move_pipeline(self):
        self.assertEqual(self.window.history_panel.table.rowCount(), 0)

        self.window.chess_board.execute_user_move(chess.E2, chess.E4)
        self.assertEqual(self.window.history_panel.table.rowCount(), 1)
        self.assertEqual(self.window.history_panel.table.item(0, 1).text(), "e4")
        self.assertIn("黑方", self.window.status_bar_label.text())
        self.assertEqual(self.window.chess_board.last_move.uci(), "e2e4")

        self.window.chess_board.execute_user_move(chess.E7, chess.E5)
        self.assertEqual(self.window.history_panel.table.item(0, 2).text(), "e5")

    def test_undo_updates_panels(self):
        self.window.chess_board.execute_user_move(chess.E2, chess.E4)
        self.assertTrue(self.window.controller.undo())
        self.assertEqual(self.window.history_panel.table.rowCount(), 0)
        self.assertIn("白方", self.window.status_bar_label.text())
        self.assertIsNone(self.window.chess_board.last_move)

    def test_chat_message_flow(self):
        self.window.chat_panel.send_message("请评估局面")
        html = self.window.chat_panel.chat_display.toHtml()
        self.assertIn("请评估局面", html)
        self.assertIn("FEN", html)

    def test_resign_and_draw_gui(self):
        from PySide6.QtWidgets import QMessageBox
        with patch("src.gui.main_window.QMessageBox.question", return_value=QMessageBox.Yes):
            with patch("src.gui.main_window.QMessageBox.information"):
                self.window.on_resign()
        self.assertTrue(self.window.controller._is_locked())
        self.assertEqual(len(self.window.controller.history_store.list_games()), 1)


if __name__ == "__main__":
    unittest.main()
