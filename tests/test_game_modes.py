import unittest

from src.controller.game_modes import GameMode, GameModeManager, MODE_LABELS


class TestGameModes(unittest.TestCase):
    def test_target_elo_and_skill_mode(self):
        manager = GameModeManager()
        manager.set_mode(GameMode.VS_ENGINE)
        manager.set_target_elo(1900)
        self.assertTrue(manager.use_elo)
        self.assertEqual(manager.target_elo, 1900)
        white, black = manager.player_names()
        self.assertIn("Elo 1900", black)

        manager.set_engine_skill(15)
        self.assertFalse(manager.use_elo)
        self.assertEqual(manager.engine_skill, 15)
        white, black = manager.player_names()
        self.assertIn("Lv.15", black)


if __name__ == "__main__":
    unittest.main()