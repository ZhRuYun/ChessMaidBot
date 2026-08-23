"""
游戏调度器 (模块2 - 调度层核心)
棋局状态的唯一写路径: GUI 只发意图 (apply/undo/new_game/resign/draw), 状态变更经信号广播
职责:
  - 走法应用、记谱、终局判定与归档 (PGN + LLM 总结)
  - 人机对弈调度 (多线程异步执行 Stockfish 走棋，避免 GUI 冻结)
  - 认输 (Resign) 与 求和 (Offer/Claim Draw) 状态机流程
  - 对弈模式与教学开关的状态保持
"""
from typing import Optional, Dict, Any, Callable

import chess
from PySide6.QtCore import QObject, Signal, QThread

from ..agents.base import AgentRequest, AgentTools, PositionSnapshot
from ..core.board_state import BoardState, GameResult
from ..core.game_record import MoveHistoryManager
from ..database.history_store import HistoryStore
from ..engine.stockfish_client import StockfishClient
from .game_modes import GameMode, GameModeManager
from .teaching_triggers import TeachingTriggers


class EngineWorker(QThread):
    """用于异步计算 Stockfish 引擎最佳着法的后台工作线程"""
    move_computed = Signal(str)  # 产出 UCI 格式着法 (如 e7e5)
    failed = Signal(str)

    def __init__(self, fen: str, skill_level: int, target_elo: Optional[int], use_elo: bool, parent=None):
        super().__init__(parent)
        self.fen = fen
        self.skill_level = skill_level
        self.target_elo = target_elo
        self.use_elo = use_elo

    def run(self):
        try:
            with StockfishClient() as client:
                if self.use_elo and self.target_elo is not None:
                    client.set_elo(self.target_elo)
                else:
                    client.set_skill_level(self.skill_level)
                uci_move = client.best_move(self.fen, movetime_ms=600)
                if uci_move:
                    self.move_computed.emit(uci_move)
                else:
                    self.failed.emit("引擎未能计算出合法着法")
        except Exception as e:
            self.failed.emit(str(e))


class GameController(QObject):
    position_changed = Signal(object)      # 最近一步 chess.Move (可为 None)
    history_changed = Signal(list)         # List[MoveRecord]
    status_changed = Signal(str, bool)     # 状态栏文本, 是否被将军
    move_played = Signal(str, str, bool)   # SAN, UCI, 是否白方走的
    game_over = Signal(dict)               # get_game_status() 结果
    game_reset = Signal()
    mode_changed = Signal(object)          # GameMode
    engine_thinking_changed = Signal(bool) # 引擎是否在思考中 (用于锁定 UI 交互)

    def __init__(self, history_store: Optional[HistoryStore] = None, parent=None):
        super().__init__(parent)
        self.board_state = BoardState()
        self.history = MoveHistoryManager()
        self.modes = GameModeManager()
        self.teaching = TeachingTriggers()
        self.history_store = history_store or HistoryStore()
        self._finalized = False
        self._engine_thread: Optional[EngineWorker] = None
        self._llm_summary_provider: Optional[Callable[[PositionSnapshot], str]] = None

    def set_llm_summary_provider(self, provider: Optional[Callable[[PositionSnapshot], str]]):
        """注入 LLM 终局总结生成函数，用于归档 'PGN + LLM 总结'"""
        self._llm_summary_provider = provider

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
            self._check_engine_turn()
        return True

    def _check_engine_turn(self):
        """人机对弈模式下，检测是否轮到引擎走棋并异步启动思考"""
        if self.modes.mode != GameMode.VS_ENGINE:
            return
        if self.board_state.is_game_over():
            return
        # 默认人类执白(先手), 引擎执黑(后手)
        if self.board_state.turn == chess.BLACK:
            self._start_engine_thinking()

    def _start_engine_thinking(self):
        if self._engine_thread is not None and self._engine_thread.isRunning():
            return

        self.engine_thinking_changed.emit(True)
        self._engine_thread = EngineWorker(
            fen=self.board_state.get_fen(),
            skill_level=self.modes.engine_skill,
            target_elo=self.modes.target_elo,
            use_elo=self.modes.use_elo,
            parent=self,
        )
        self._engine_thread.move_computed.connect(self._on_engine_move_ready)
        self._engine_thread.failed.connect(self._on_engine_move_failed)
        self._engine_thread.start()

    def _on_engine_move_ready(self, uci_move: str):
        self.engine_thinking_changed.emit(False)
        try:
            move = chess.Move.from_uci(uci_move)
            self.apply_move(move)
        except Exception:
            pass

    def _on_engine_move_failed(self, error_msg: str):
        self.engine_thinking_changed.emit(False)

    def undo(self) -> bool:
        """悔棋一步; 若在人机模式下若轮到玩家，则自动撤销两步(玩家+引擎)"""
        self._stop_engine_thread()

        if self.modes.mode == GameMode.VS_ENGINE and self.board_state.turn == chess.WHITE and len(self.board_state.board.move_stack) >= 2:
            # 撤销引擎步与玩家步
            self.board_state.undo_move()
            self.history.pop_move()
            self.board_state.undo_move()
            self.history.pop_move()
            self._finalized = False
            self.position_changed.emit(self.board_state.last_move)
            self.history_changed.emit(list(self.history.records))
            self._emit_status()
            return True

        if not self.board_state.undo_move():
            return False
        self._finalized = False
        self.history.pop_move()
        self.position_changed.emit(self.board_state.last_move)
        self.history_changed.emit(list(self.history.records))
        self._emit_status()
        return True

    def resign(self, is_white: bool) -> bool:
        """指定方认输 (产生胜负并归档)"""
        if self._is_locked():
            return False
        self._stop_engine_thread()

        winner = "Black" if is_white else "White"
        loser_cn = "白方" if is_white else "黑方"
        result = GameResult.BLACK_WINS if is_white else GameResult.WHITE_WINS
        status = {
            "is_over": True,
            "is_check": self.board_state.is_check(),
            "is_checkmate": False,
            "is_stalemate": False,
            "is_insufficient_material": False,
            "is_seventyfive_moves": False,
            "is_fivefold_repetition": False,
            "can_claim_fifty_moves": False,
            "can_claim_threefold_repetition": False,
            "result": result,
            "reason": f"{loser_cn}认输 (Resignation). {winner} 获胜。",
        }
        self._finalize_game(status, override_result=result)
        return True

    def offer_draw(self) -> Dict[str, Any]:
        """提和/认领和棋：
        1. 若符合三度重复或50步规则，直接判定并归档和棋；
        2. 若在人机模式，由引擎估分决定是否接受和棋（分差绝对值小则同意）；
        3. 若在本地双人模式，返回需对方确认标识。
        """
        if self._is_locked():
            return {"accepted": False, "reason": "对局已结束"}
        self._stop_engine_thread()

        # 规则申诉和棋 (50步规则或3次重复局面)
        if self.board_state.board.can_claim_fifty_moves() or self.board_state.board.can_claim_threefold_repetition():
            return self.accept_draw(reason="和棋申诉成功 (50步规则 / 三度重复局面)")

        if self.modes.mode == GameMode.VS_ENGINE:
            # 引擎根据评估决定是否接受
            try:
                with StockfishClient() as client:
                    state = client.get_state(self.board_state.get_fen(), state_type="analyse", depth=8)
                    analysis = state.get("analysis", [])
                    if analysis and analysis[0].get("score_cp") is not None:
                        cp = analysis[0]["score_cp"]
                        # 引擎在劣势不大或均势 (分差在 ±100 cp 以内) 时接受和棋
                        if abs(cp) <= 120:
                            return self.accept_draw(reason="Stockfish 评估局面均势，同意和棋请求。")
                        else:
                            return {"accepted": False, "reason": "Stockfish 认为当前处于优势，拒绝了和棋请求。"}
            except Exception:
                pass
            return self.accept_draw(reason="双方协议和棋。")

        return {"accepted": True, "requires_confirm": True, "reason": "已发起求和请求，等待确认。"}

    def accept_draw(self, reason: str = "双方协议和棋 (Draw by agreement)") -> Dict[str, Any]:
        """确认达成和棋并归档"""
        if self._is_locked():
            return {"accepted": False, "reason": "对局已结束"}
        self._stop_engine_thread()

        status = {
            "is_over": True,
            "is_check": self.board_state.is_check(),
            "is_checkmate": False,
            "is_stalemate": False,
            "is_insufficient_material": False,
            "is_seventyfive_moves": False,
            "is_fivefold_repetition": False,
            "can_claim_fifty_moves": False,
            "can_claim_threefold_repetition": False,
            "result": GameResult.DRAW,
            "reason": reason,
        }
        self._finalize_game(status, override_result=GameResult.DRAW)
        return {"accepted": True, "reason": reason}

    def _stop_engine_thread(self):
        if self._engine_thread is not None:
            if self._engine_thread.isRunning():
                self._engine_thread.terminate()
                self._engine_thread.wait(500)
            self._engine_thread = None
            self.engine_thinking_changed.emit(False)

    def new_game(self, fen: Optional[str] = None):
        self._stop_engine_thread()
        self.board_state.reset(fen)
        self._apply_mode_headers()
        self.history.clear()
        self._finalized = False
        self.game_reset.emit()
        self.position_changed.emit(None)
        self.history_changed.emit([])
        self._emit_status()
        self._check_engine_turn()

    def _is_locked(self) -> bool:
        return self._finalized or self.board_state.is_game_over()

    def _emit_status(self):
        in_check = self.board_state.is_check()
        turn_str = "白方 (White)" if self.board_state.turn == chess.WHITE else "黑方 (Black)"
        text = f"当前行动: {turn_str} ⚠️ [ 被将军 Check! ]" if in_check else f"当前行动: {turn_str}"
        self.status_changed.emit(text, in_check)

    def _apply_mode_headers(self):
        white_name, black_name = self.modes.player_names()
        self.board_state.custom_headers["White"] = white_name
        self.board_state.custom_headers["Black"] = black_name

    def _finalize_game(self, status: dict, override_result: Optional[str] = None):
        """终局处理: 补全对局头并以 'PGN + LLM 总结' 格式归档到历史棋局库"""
        self._stop_engine_thread()
        self._apply_mode_headers()
        status = dict(status)
        result_str = override_result or status.get("result", "*")

        if not self._finalized:
            self._finalized = True
            llm_summary = None
            if self._llm_summary_provider:
                try:
                    llm_summary = self._llm_summary_provider(self.get_snapshot())
                except Exception:
                    llm_summary = None

            if not llm_summary:
                llm_summary = f"对局结束，结果为 {result_str}。终局原因: {status.get('reason', '')}"

            try:
                self.history_store.save_game(
                    pgn_text=self.board_state.export_pgn(override_result=result_str),
                    result=result_str,
                    llm_summary=llm_summary,
                )
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
        self._stop_engine_thread()
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
        else:
            self._check_engine_turn()
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

    # ---------- 模式、引擎参数与教学开关 ----------

    def set_mode_label(self, label: str) -> GameMode:
        self._stop_engine_thread()
        mode = self.modes.set_mode_by_label(label)
        self._apply_mode_headers()
        self.mode_changed.emit(mode)
        self._check_engine_turn()
        return mode

    def set_mode(self, mode: GameMode):
        self._stop_engine_thread()
        self.modes.set_mode(mode)
        self._apply_mode_headers()
        self.mode_changed.emit(mode)
        self._check_engine_turn()

    def set_engine_elo(self, elo: int):
        """设置 Stockfish 目标 Elo 等级分"""
        self.modes.set_target_elo(elo)
        self._apply_mode_headers()

    def set_engine_skill(self, skill: int):
        """设置 Stockfish 技能等级 (0-20)"""
        self.modes.set_engine_skill(skill)
        self._apply_mode_headers()

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
        params = dict(params or {})
        # 默认填入当前局面 FEN 方便开局/残局直接查询
        if "fen" not in params and category in ("opening", "tactics", "endgame"):
            params["fen"] = self.board_state.get_fen()
        return self.history_store.query_database(category=category, **params)

    def _agent_read_engine_state(self, state_type: str = "best_move", params: Optional[Dict[str, Any]] = None) -> Any:
        """为 LLM 提供的 Stockfish 状态读取方法 (模块5方法 3 & 4)"""
        params = params or {}
        with StockfishClient() as client:
            if self.modes.use_elo and self.modes.target_elo is not None:
                client.set_elo(self.modes.target_elo)
            else:
                client.set_skill_level(self.modes.engine_skill)
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

