"""
游戏调度器 (模块2 - 调度层核心)
棋局状态的唯一写路径: GUI 只发意图 (apply/undo/new_game), 状态变更经信号广播
职责: 走法应用、记谱、终局判定与归档、对弈模式与教学开关的状态保持
"""
from typing import Optional, Dict, Any

import chess
from PySide6.QtCore import QObject, Signal

from ..agents.base import AgentRequest, AgentTools, PositionSnapshot
from ..core.board_state import BoardState
from ..core.game_record import MoveHistoryManager
from ..database.history_store import HistoryStore
from ..engine.stockfish_client import StockfishClient
from .game_modes import GameMode, GameModeManager
from .teaching_triggers import TeachingTriggers


class GameController(QObject):
    position_changed = Signal(object)      # 最近一步 chess.Move (可为 None)
    history_changed = Signal(list)         # List[MoveRecord]
    status_changed = Signal(str, bool)     # 状态栏文本, 是否被将军
    move_played = Signal(str, str, bool)   # SAN, UCI, 是否白方走的
    game_over = Signal(dict)               # get_game_status() 结果
    game_reset = Signal()
    mode_changed = Signal(object)          # GameMode

    def __init__(self, history_store: Optional[HistoryStore] = None, parent=None):
        super().__init__(parent)
        self.board_state = BoardState()
        self.history = MoveHistoryManager()
        self.modes = GameModeManager()
        self.teaching = TeachingTriggers()
        self.history_store = history_store or HistoryStore()
        self._finalized = False

    # ---------- 走法与对局流程 ----------

    def apply_move(self, move: chess.Move) -> bool:
        """应用一步走法 (棋局结束后拒绝)"""
        if self._is_locked():
            return False

        was_white = self.board_state.turn == chess.WHITE
        ok, san, _captured = self.board_state.make_move(move)
        if not ok:
            return False

        self.history.add_move(san, was_white, self.board_state.get_fen())
        self.position_changed.emit(self.board_state.last_move)
        self.history_changed.emit(list(self.history.records))
        self.move_played.emit(san, move.uci(), was_white)

        status = self.board_state.get_game_status()
        if status["is_over"]:
            self._finalize_game(status)
        else:
            self._emit_status()
        return True

    def undo(self) -> bool:
        """悔棋一步; 若终局已归档则允许继续对局"""
        if not self.board_state.undo_move():
            return False
        self._finalized = False
        self.history.pop_move()
        self.position_changed.emit(self.board_state.last_move)
        self.history_changed.emit(list(self.history.records))
        self._emit_status()
        return True

    def new_game(self, fen: Optional[str] = None):
        self.board_state.reset(fen)
        self._apply_mode_headers()
        self.history.clear()
        self._finalized = False
        self.game_reset.emit()
        self.position_changed.emit(None)
        self.history_changed.emit([])
        self._emit_status()

    def _is_locked(self) -> bool:
        return self.board_state.is_game_over()

    def _emit_status(self):
        in_check = self.board_state.is_check()
        turn_str = "白方 (White)" if self.board_state.turn == chess.WHITE else "黑方 (Black)"
        text = f"当前行动: {turn_str} ⚠️ [ 被将军 Check! ]" if in_check else f"当前行动: {turn_str}"
        self.status_changed.emit(text, in_check)

    def _apply_mode_headers(self):
        white_name, black_name = self.modes.player_names()
        self.board_state.custom_headers["White"] = white_name
        self.board_state.custom_headers["Black"] = black_name

    def _finalize_game(self, status: dict):
        """终局处理: 补全对局头并归档到历史棋局库"""
        self._apply_mode_headers()
        status = dict(status)
        if not self._finalized:
            self._finalized = True
            try:
                self.history_store.save_game(self.board_state.export_pgn(), status.get("result", "*"))
            except OSError:
                pass  # 归档失败不阻断对局结束流程
        self.game_over.emit(status)
        self._emit_status()

    # ---------- 导入导出 ----------

    def export_pgn(self) -> str:
        self._apply_mode_headers()
        return self.board_state.export_pgn()

    def get_fen(self) -> str:
        return self.board_state.get_fen()

    def import_pgn(self, pgn_text: str) -> bool:
        if not self.board_state.import_pgn(pgn_text):
            return False
        self._rebuild_history_from_board()
        self._finalized = False
        self.position_changed.emit(self.board_state.last_move)
        self.history_changed.emit(list(self.history.records))
        self._emit_status()
        status = self.board_state.get_game_status()
        if status["is_over"]:
            self._finalize_game(status)
        return True

    def _rebuild_history_from_board(self):
        """依据走法栈重建双栏记谱 (兼容黑先开局的 FEN/PGN)"""
        self.history.clear()
        replay = self.board_state.board.copy()
        while replay.move_stack:
            replay.pop()
        for san in self.board_state.move_stack_san:
            is_white = replay.turn == chess.WHITE
            replay.push_san(san)
            self.history.add_move(san, is_white, replay.fen())

    # ---------- 模式与教学开关 ----------

    def set_mode_label(self, label: str) -> GameMode:
        mode = self.modes.set_mode_by_label(label)
        self._apply_mode_headers()
        self.mode_changed.emit(mode)
        return mode

    def set_mode(self, mode: GameMode):
        self.modes.set_mode(mode)
        self._apply_mode_headers()
        self.mode_changed.emit(mode)

    def set_teaching(self, triggers: TeachingTriggers):
        self.teaching = triggers

    # ---------- Agent 上下文 ----------

    def get_snapshot(self) -> PositionSnapshot:
        status = self.board_state.get_game_status()
        return PositionSnapshot(
            fen=self.board_state.get_fen(),
            pgn=self.export_pgn(),
            turn="白方" if self.board_state.turn == chess.WHITE else "黑方",
            legal_move_count=self.board_state.legal_move_count(),
            in_check=self.board_state.is_check(),
            last_move_san=self.history.last_san(),
            game_over_reason=status["reason"] if status["is_over"] else "",
        )

    def _agent_read_database(self, category: str = "history", params: Optional[Dict[str, Any]] = None) -> Any:
        """为 LLM 提供的数据库读取方法 (模块5方法 1 & 2)"""
        params = params or {}
        return self.history_store.query_database(category=category, **params)

    def _agent_read_engine_state(self, state_type: str = "best_move", params: Optional[Dict[str, Any]] = None) -> Any:
        """为 LLM 提供的 Stockfish 状态读取方法 (模块5方法 3 & 4)"""
        params = params or {}
        with StockfishClient() as client:
            return client.get_state(fen=self.board_state.get_fen(), state_type=state_type, **params)

    def build_agent_request(self, user_message: str, persona_prompt: str) -> AgentRequest:
        tools = AgentTools(
            read_database=self._agent_read_database,
            read_engine_state=self._agent_read_engine_state,
        )
        return AgentRequest(
            user_message=user_message,
            persona_prompt=persona_prompt,
            snapshot=self.get_snapshot(),
            tools=tools,
        )
