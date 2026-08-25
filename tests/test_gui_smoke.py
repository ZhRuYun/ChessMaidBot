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
        if self.window._llm_thread and self.window._llm_thread.isRunning():
            self.window._llm_thread.wait(500)
        self.tmp.cleanup()

    def test_full_move_pipeline(self):
        self.assertEqual(self.window.history_panel.table.rowCount(), 0)

        # 走白方
        self.window.chess_board.execute_user_move(chess.E2, chess.E4)
        if self.window._llm_thread is not None:
            self.window._llm_thread.wait(1000)
            APP.processEvents()
        self.assertEqual(self.window.history_panel.table.rowCount(), 1)
        self.assertEqual(self.window.history_panel.table.item(0, 1).text(), "e4")
        self.assertIn("黑方", self.window.status_bar_label.text())
        self.assertEqual(self.window.chess_board.last_move.uci(), "e2e4")

        # 走黑方
        self.window.chess_board.execute_user_move(chess.E7, chess.E5)
        if self.window._llm_thread is not None:
            self.window._llm_thread.wait(1000)
            APP.processEvents()
        self.assertEqual(self.window.history_panel.table.item(0, 2).text(), "e5")

    def test_undo_updates_panels(self):
        self.window.chess_board.execute_user_move(chess.E2, chess.E4)
        if self.window._llm_thread is not None:
            self.window._llm_thread.wait(1000)
            APP.processEvents()
        self.assertTrue(self.window.controller.undo())
        self.assertEqual(self.window.history_panel.table.rowCount(), 0)
        self.assertIn("白方", self.window.status_bar_label.text())
        self.assertIsNone(self.window.chess_board.last_move)

    def test_chat_message_flow(self):
        self.window.chat_panel.send_message("请评估局面")
        if self.window._llm_thread is not None:
            self.window._llm_thread.wait(1000)
            APP.processEvents()
        html = self.window.chat_panel.chat_display.toHtml()
        self.assertIn("请评估局面", html)
        self.assertIn("FEN", html)

    def test_export_game_state_to_clipboard(self):
        self.window.chess_board.execute_user_move(chess.E2, chess.E4)
        if self.window._llm_thread is not None:
            self.window._llm_thread.wait(1000)
            APP.processEvents()
        with patch("src.gui.main_window.QMessageBox.information"):
            self.window.on_export_game_state()
        clipboard_text = QApplication.clipboard().text()
        self.assertIn("=== PGN ===", clipboard_text)
        self.assertIn("1. e4", clipboard_text)
        self.assertIn("=== FEN ===", clipboard_text)

    def test_ask_llm_button_flow(self):
        self.window.on_ask_llm_requested()
        if self.window._llm_thread is not None:
            self.window._llm_thread.wait(1000)
            APP.processEvents()
        html = self.window.chat_panel.chat_display.toHtml()
        self.assertIn("主动询问女仆指导", html)

    def test_resign_and_draw_gui(self):
        from PySide6.QtWidgets import QMessageBox
        # 先下几步再认输，以生成有效棋局
        self.window.chess_board.execute_user_move(chess.E2, chess.E4)
        if self.window._llm_thread is not None:
            self.window._llm_thread.wait(1000)
            APP.processEvents()
        self.window.chess_board.execute_user_move(chess.E7, chess.E5)
        if self.window._llm_thread is not None:
            self.window._llm_thread.wait(1000)
            APP.processEvents()
        with patch("src.gui.main_window.QMessageBox.question", return_value=QMessageBox.Yes):
            with patch("src.gui.main_window.QMessageBox.information"):
                self.window.on_resign()
        self.assertTrue(self.window.controller._is_locked())
        self.assertEqual(len(self.window.controller.history_store.list_games()), 1)

    def test_new_game_during_engine_match_resets_board(self):
        """回归测试: 人机模式下对局中点「新局」应正常重置棋盘
        (曾因访问 chess_board.flipped 属性名错误抛 AttributeError, 导致 new_game 永不执行)"""
        from PySide6.QtWidgets import QMessageBox
        from src.controller.game_modes import GameMode

        self.window.controller.set_mode(GameMode.VS_ENGINE)
        self.window.controller.apply_move(chess.Move.from_uci("e2e4"))
        if self.window._llm_thread is not None:
            self.window._llm_thread.wait(1000)
            APP.processEvents()
        self.window.controller.apply_move(chess.Move.from_uci("e7e5"))
        if self.window._llm_thread is not None:
            self.window._llm_thread.wait(1000)
            APP.processEvents()
        self.assertEqual(len(self.window.controller.board_state.board.move_stack), 2)

        class _FakeBtn:
            pass

        # 模拟用户点击「新局」→ 确认 → 选边对话框中选择执白
        chosen_btn = _FakeBtn()
        with patch("src.gui.main_window.QMessageBox.question", return_value=QMessageBox.Yes), \
             patch("src.gui.main_window.QMessageBox.exec", new=lambda self: None), \
             patch("src.gui.main_window.QMessageBox.addButton", new=lambda self, text, role: _FakeBtn()), \
             patch("src.gui.main_window.QMessageBox.clickedButton", new=lambda self: chosen_btn):
            self.window.on_new_game()  # 不应抛出 AttributeError

        APP.processEvents()
        self.assertEqual(len(self.window.controller.board_state.board.move_stack), 0)
        self.assertEqual(self.window.controller.get_fen(), chess.STARTING_FEN)
        self.assertEqual(self.window.history_panel.table.rowCount(), 0)


if __name__ == "__main__":
    unittest.main()

