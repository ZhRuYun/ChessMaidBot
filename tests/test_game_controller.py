"""
调度层: 对弈模式 / 教学触发器 / 游戏调度器 单元测试
"""
import tempfile
import unittest
from pathlib import Path

import chess

from src.controller.game_controller import GameController
from src.controller.game_modes import GameMode, GameModeManager, MODE_LABELS
from src.controller.teaching_triggers import TeachingTriggers
from src.core.board_state import GameResult
from src.database.history_store import HistoryStore

SCHOLAR_MATE = ["e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"]


class TestGameModeManager(unittest.TestCase):
    def test_label_roundtrip(self):
        manager = GameModeManager()
        for mode, label in MODE_LABELS.items():
            self.assertEqual(manager.set_mode_by_label(label), mode)
            self.assertEqual(manager.mode, mode)

    def test_unknown_label_keeps_mode(self):
        manager = GameModeManager()
        manager.set_mode(GameMode.VS_ENGINE)
        self.assertEqual(manager.set_mode_by_label("不存在的模式"), GameMode.VS_ENGINE)

    def test_engine_skill_clamped(self):
        manager = GameModeManager()
        manager.set_engine_skill(99)
        self.assertEqual(manager.engine_skill, 20)
        manager.set_engine_skill(-5)
        self.assertEqual(manager.engine_skill, 0)

    def test_player_names_by_mode(self):
        manager = GameModeManager()
        self.assertEqual(manager.player_names(), ("Player 1", "Player 2"))
        manager.set_mode(GameMode.VS_ENGINE)
        white, black = manager.player_names()
        self.assertEqual(black, "Stockfish (Elo 1500)")
        manager.set_engine_skill(10)
        white, black = manager.player_names()
        self.assertEqual(black, "Stockfish (Lv.10)")
        manager.set_mode(GameMode.VS_MAID_LLM)
        self.assertEqual(manager.player_names()[1], "ChessMaid")


class TestTeachingTriggers(unittest.TestCase):
    def test_active_requires_master_and_any_sub(self):
        triggers = TeachingTriggers()
        self.assertTrue(triggers.active)

        triggers.master_enabled = False
        self.assertFalse(triggers.active)

        triggers.master_enabled = True
        triggers.eval_current_position = False
        triggers.suggest_moves = False
        triggers.eval_history_moves = False
        triggers.game_over_summary = False
        self.assertFalse(triggers.active)


class TestGameController(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = HistoryStore(root=Path(self.tmp.name))
        self.controller = GameController(history_store=self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def _play(self, ucis):
        for uci in ucis:
            self.assertTrue(self.controller.apply_move(chess.Move.from_uci(uci)))

    def test_apply_move_updates_history_and_signals(self):
        events = []
        self.controller.move_played.connect(lambda san, uci, w: events.append((san, uci, w)))
        self.controller.history_changed.connect(lambda records: events.append(("history", len(records))))

        self._play(["e2e4"])
        self.assertEqual(self.controller.history.records[0].white_san, "e4")
        self.assertIn(("e4", "e2e4", True), events)

    def test_reject_move_after_game_over(self):
        self._play(SCHOLAR_MATE)
        self.assertFalse(self.controller.apply_move(chess.Move.from_uci("a2a3")))

    def test_game_over_saves_pgn_to_history_store(self):
        over_events = []
        self.controller.game_over.connect(lambda status: over_events.append(status))

        self._play(SCHOLAR_MATE)
        self.assertEqual(len(over_events), 1)
        self.assertEqual(over_events[0]["result"], GameResult.WHITE_WINS)

        games = self.store.list_games()
        self.assertEqual(len(games), 1)
        content = HistoryStore.load_text(games[0])
        self.assertIn("[Result \"1-0\"]", content)
        self.assertIn("Qxf7#", content)

    def test_undo_after_game_over_allows_continuing(self):
        over_events = []
        self.controller.game_over.connect(lambda status: over_events.append(status))

        self._play(SCHOLAR_MATE)
        self.assertEqual(len(over_events), 1)
        self.assertEqual(len(self.store.list_games()), 1)

        # 悔掉 Qxf7# 后轮到白方, 可重新走出杀招并再次归档
        self.assertTrue(self.controller.undo())
        self.assertTrue(self.controller.apply_move(chess.Move.from_uci("h5f7")))
        self.assertEqual(len(over_events), 2)
        self.assertEqual(len(self.store.list_games()), 2)

    def test_new_game_resets(self):
        self._play(["e2e4"])
        reset_events = []
        self.controller.game_reset.connect(lambda: reset_events.append(True))

        self.controller.new_game()
        self.assertEqual(self.controller.history.records, [])
        self.assertEqual(self.controller.board_state.get_fen(), chess.STARTING_FEN)
        self.assertTrue(reset_events)

    def test_undo_at_start_returns_false(self):
        self.assertFalse(self.controller.undo())

    def test_import_pgn_rebuilds_history(self):
        self._play(["e2e4", "e7e5", "g1f3", "b8c6"])
        pgn_text = self.controller.export_pgn()

        self.controller.new_game()
        self.assertTrue(self.controller.import_pgn(pgn_text))
        self.assertEqual(len(self.controller.history.records), 2)
        self.assertEqual(self.controller.history.records[0].white_san, "e4")
        self.assertEqual(self.controller.history.records[0].black_san, "e5")
        self.assertEqual(self.controller.history.records[1].white_san, "Nf3")
        self.assertEqual(self.controller.history.records[1].black_san, "Nc6")

    def test_snapshot_and_agent_request(self):
        self._play(["e2e4"])
        snapshot = self.controller.get_snapshot()
        self.assertEqual(snapshot.turn, "黑方")
        self.assertFalse(snapshot.in_check)
        self.assertEqual(snapshot.last_move_san, "e4")
        self.assertIn("1. e4", snapshot.pgn)

        request = self.controller.build_agent_request("你好", persona_prompt="人设")
        self.assertEqual(request.user_message, "你好")
        self.assertEqual(request.persona_prompt, "人设")
        self.assertEqual(request.snapshot.fen, snapshot.fen)
        self.assertIsNotNone(request.tools)
        self.assertIsNotNone(request.tools.read_database)
        self.assertIsNotNone(request.tools.read_engine_state)

        # 验证 Agent 工具调用
        db_res = request.tools.read_database("history")
        self.assertEqual(db_res["category"], "history")

    def test_resign_workflow(self):
        over_events = []
        self.controller.game_over.connect(lambda status: over_events.append(status))

        self._play(["e2e4"])
        # 白方认输 -> 黑方获胜
        self.assertTrue(self.controller.resign(is_white=True))
        self.assertEqual(len(over_events), 1)
        self.assertEqual(over_events[0]["result"], GameResult.BLACK_WINS)
        self.assertIn("认输", over_events[0]["reason"])

        # 验证持久化了 PGN + 总结
        games = self.store.list_games()
        self.assertEqual(len(games), 1)
        parsed = HistoryStore.parse_game_file(HistoryStore.load_text(games[0]))
        self.assertIn("0-1", parsed["pgn"])
        self.assertIn("对局结束", parsed["summary"])

    def test_draw_workflow(self):
        over_events = []
        self.controller.game_over.connect(lambda status: over_events.append(status))

        self._play(["e2e4", "e7e5"])
        res = self.controller.accept_draw("双方协议和棋")
        self.assertTrue(res["accepted"])
        self.assertEqual(len(over_events), 1)
        self.assertEqual(over_events[0]["result"], GameResult.DRAW)

    def test_target_elo_and_skill_controller(self):
        self.controller.set_engine_elo(1650)
        self.assertEqual(self.controller.modes.target_elo, 1650)
        self.assertTrue(self.controller.modes.use_elo)

        self.controller.set_engine_skill(12)
        self.assertEqual(self.controller.modes.engine_skill, 12)
        self.assertFalse(self.controller.modes.use_elo)


if __name__ == "__main__":
    unittest.main()
