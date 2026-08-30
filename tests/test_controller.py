import unittest
import chess
from src.controller.game_controller import GameController
from src.controller.game_modes import GameMode
from src.controller.teaching_triggers import TeachingTriggers


class TestController(unittest.TestCase):
    def test_game_controller_flow(self):
        ctrl = GameController()
        self.assertEqual(ctrl.modes.mode, GameMode.LOCAL_PVP)
        self.assertEqual(ctrl.board_state.turn, chess.WHITE)

        # Apply legal move
        success = ctrl.apply_move(chess.Move.from_uci("e2e4"))
        self.assertTrue(success)
        self.assertEqual(ctrl.board_state.turn, chess.BLACK)
        self.assertEqual(len(ctrl.history.records), 1)

        # Undo move
        undone = ctrl.undo()
        self.assertTrue(undone)
        self.assertEqual(ctrl.board_state.turn, chess.WHITE)
        self.assertEqual(len(ctrl.history.records), 0)

    def test_game_controller_resign_and_draw(self):
        ctrl = GameController()
        ctrl.apply_move(chess.Move.from_uci("e2e4"))
        ctrl.apply_move(chess.Move.from_uci("e7e5"))

        # Resign
        ctrl.resign(is_white=False)
        self.assertTrue(ctrl._is_locked())

        # New game
        ctrl.new_game()
        self.assertFalse(ctrl._is_locked())
        self.assertEqual(len(ctrl.history.records), 0)

        # Draw
        ctrl.offer_draw()
        ctrl.accept_draw()
        self.assertTrue(ctrl._is_locked())

    def test_teaching_triggers(self):
        triggers = TeachingTriggers()
        self.assertTrue(triggers.master_enabled)
        self.assertTrue(triggers.active)

        triggers.master_enabled = False
        self.assertFalse(triggers.active)

        triggers.master_enabled = True
        triggers.eval_current_position = False
        self.assertTrue(triggers.active)


if __name__ == "__main__":
    unittest.main()
