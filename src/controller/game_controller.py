"""
游戏调度器 (模块2 - 调度层核心)
棋局状态的唯一写路径: GUI 只发意图 (apply/undo/new_game/resign/draw), 状态变更经信号广播
职责:
  - 走法应用、记谱、终局判定与归档 (PGN + LLM 总结, 后台线程落盘避免阻塞 UI)
  - 人机对弈调度 (多线程异步执行 Stockfish 走棋，避免 GUI 冻结)
  - 认输 (Resign) 与 求和 (Offer/Claim Draw) 状态机流程
  - 对弈模式与教学开关的状态保持

线程安全设计:
  - 引擎调用统一走 shared_engine (进程级互斥复用), 不会产生 UCI 协议交错
  - 过期异步结果通过「代际 (generation) 丢弃」机制失效, 不使用 terminate()
    (强杀持锁线程会导致共享引擎死锁)
"""
import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from typing import Optional, Dict, Any, Callable, List

import chess
from PySide6.QtCore import QObject, Signal, QThread

from ..agents.base import AgentRequest, AgentTools, PositionSnapshot
from ..core.board_state import BoardState, GameResult
from ..core.game_record import MoveHistoryManager
from ..database.history_store import HistoryStore
from ..engine.stockfish_client import shared_engine
from .game_modes import GameMode, GameModeManager
from .teaching_triggers import TeachingTriggers

logger = logging.getLogger("chessmaid.controller")


class EngineWorker(QThread):
    """用于异步计算 Stockfish 引擎或 Maid LLM 最佳着法的后台工作线程

    线程安全: AgentRequest 在主线程预构建 (快照冻结), 本线程不再触碰棋局状态;
    cancel_event 由控制器置位, 贯通到 LLM HTTP 读取循环及时中止, 避免空烧 Token。
    """
    move_computed = Signal(str, int, str)  # (UCI 着法, 代际号, 着法来源 "llm"/"engine")
    failed = Signal(str, int)              # (错误信息, 代际号)

    def __init__(
        self,
        fen: str,
        skill_level: int,
        target_elo: Optional[int],
        use_elo: bool,
        generation: int = 0,
        is_maid_llm: bool = False,
        agent_request: Optional[AgentRequest] = None,
        agent: Optional[Any] = None,
        cancel_event: Optional[threading.Event] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.fen = fen
        self.skill_level = skill_level
        self.target_elo = target_elo
        self.use_elo = use_elo
        self.generation = generation
        self.is_maid_llm = is_maid_llm
        self.agent_request = agent_request
        self.agent = agent
        self.cancel_event = cancel_event
        # 线程结束自动回收 C++ / Python 资源，杜绝对象在长会话中累积泄漏
        self.finished.connect(self.deleteLater)

    def _best_move_via_engine(self) -> Optional[str]:
        """通过共享引擎进程计算最佳着法 (线程安全串行)"""

        def _run(client):
            if self.use_elo and self.target_elo is not None:
                client.set_elo(self.target_elo)
            else:
                client.set_skill_level(self.skill_level)
            return client.best_move(self.fen, movetime_ms=600)

        return shared_engine.call(_run)

    def run(self):
        try:
            if self.is_maid_llm and self.agent and self.agent_request:
                is_cancelled = (lambda: self.cancel_event.is_set()) if self.cancel_event else None
                uci_move = self.agent.get_move(self.agent_request, is_cancelled=is_cancelled)
                source = getattr(self.agent, "last_move_source", None) or "engine"
                if uci_move:
                    self.move_computed.emit(uci_move, self.generation, source)
                    return
                # LLM 与内置引擎工具均未给出着法 -> 走通用引擎通道
                uci_move = self._best_move_via_engine()
                if uci_move:
                    self.move_computed.emit(uci_move, self.generation, "engine")
                else:
                    self.failed.emit("引擎未能计算出合法着法", self.generation)
                return

            uci_move = self._best_move_via_engine()
            if uci_move:
                self.move_computed.emit(uci_move, self.generation, "engine")
            else:
                self.failed.emit("引擎未能计算出合法着法", self.generation)
        except Exception as e:
            logger.error("EngineWorker 执行失败: %s", e, exc_info=True)
            self.failed.emit(str(e), self.generation)


class GameController(QObject):
    position_changed = Signal(object)      # 最近一步 chess.Move (可为 None)
    history_changed = Signal(list)         # List[MoveRecord]
    status_changed = Signal(str, bool)     # 状态栏文本, 是否被将军
    move_played = Signal(str, str, bool)   # SAN, UCI, 是否白方走的
    game_over = Signal(dict)               # get_game_status() 结果
    game_reset = Signal()
    mode_changed = Signal(object)          # GameMode
    engine_thinking_changed = Signal(bool) # 引擎是否在思考中 (用于锁定 UI 交互)
    engine_error = Signal(str)             # 引擎启动或计算失败的可见错误
    undo_requested_by_llm = Signal(str)    # LLM 劣势时向玩家发起的悔棋请求理由
    llm_fallback_used = Signal(str)        # LLM 走棋不可用时降级引擎代走的来源披露

    def __init__(self, history_store: Optional[HistoryStore] = None, parent=None):
        super().__init__(parent)
        self.board_state = BoardState()
        self.history = MoveHistoryManager()
        self.modes = GameModeManager()
        self.teaching = TeachingTriggers()
        self.history_store = history_store or HistoryStore()
        self._finalized = False
        self._engine_thread: Optional[EngineWorker] = None
        self._engine_generation = 0  # 引擎思考代际号: 每次停止/重置自增, 旧线程结果按代际丢弃
        self._engine_cancel_event: Optional[threading.Event] = None  # 在途 LLM/引擎思考的取消标志
        self._llm_summary_provider: Optional[Callable[[PositionSnapshot], str]] = None
        self._agent: Optional[Any] = None
        # 联网搜索工具的自定义接口配置 (由 MainWindow 依据持久化 settings.json 注入)
        self.search_api_url: str = ""
        self.search_api_key: str = ""

    def set_agent(self, agent: Any):
        """设置用于女仆陪练模式的 Agent 实例"""
        self._agent = agent

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
        """人机/女仆对弈模式下，检测是否轮到对方走棋并异步启动思考"""
        if self.modes.mode not in (GameMode.VS_ENGINE, GameMode.VS_MAID_LLM):
            return
        if self.board_state.is_game_over():
            return
        # 根据玩家所选执棋颜色判定是否轮到 AI
        bot_turn = (chess.WHITE if self.modes.player_side == "black" else chess.BLACK)
        if self.board_state.turn == bot_turn:
            self._start_engine_thinking()

    def _start_engine_thinking(self):
        # 允许旧线程与新线程并存: 引擎调用经 shared_engine 串行, 结果按代际丢弃,
        # 避免旧实现 terminate() 强杀线程导致的死锁与协议失步风险。
        is_maid_llm = (self.modes.mode == GameMode.VS_MAID_LLM)
        # 快照与请求在主线程预构建 (冻结), 后台线程不再读取可变棋局状态, 消除竞态
        agent_request = None
        if is_maid_llm and self._agent is not None:
            try:
                agent_request = self.build_agent_request(user_message="", persona_prompt="")
            except Exception:
                agent_request = None
        cancel_event = threading.Event()
        self._engine_cancel_event = cancel_event
        self._engine_generation += 1
        generation = self._engine_generation
        self.engine_thinking_changed.emit(True)
        self._engine_thread = EngineWorker(
            fen=self.board_state.get_fen(),
            skill_level=self.modes.engine_skill,
            target_elo=self.modes.target_elo,
            use_elo=self.modes.use_elo,
            generation=generation,
            is_maid_llm=is_maid_llm,
            agent_request=agent_request,
            agent=self._agent,
            cancel_event=cancel_event,
            parent=self,
        )
        self._engine_thread.move_computed.connect(self._on_engine_move_ready)
        self._engine_thread.failed.connect(self._on_engine_move_failed)
        self._engine_thread.start()

    def _on_engine_move_ready(self, uci_move: str, generation: int, source: str = "engine"):
        if generation != self._engine_generation:
            return  # 过期结果 (对局已被重置/悔棋), 直接丢弃
        self.engine_thinking_changed.emit(False)
        if source != "llm":
            # LLM 不可用降级代走: 明确向 UI 披露, 避免用户误认为 LLM 在走棋
            logger.warning("LLM 走棋不可用，本步由 %s 代走", source)
            self.llm_fallback_used.emit(source)
        try:
            move = chess.Move.from_uci(uci_move)
        except ValueError as exc:
            self.engine_error.emit(f"引擎返回了无效着法 {uci_move!r}: {exc}")
            return
        if not self.apply_move(move):
            self.engine_error.emit(f"引擎返回的着法 {uci_move} 在当前局面中不合法。")

    def _on_engine_move_failed(self, error_msg: str, generation: int):
        if generation != self._engine_generation:
            return
        self.engine_thinking_changed.emit(False)
        self.engine_error.emit(error_msg)

    def undo(self) -> bool:
        """悔棋一步; 若在人机/女仆陪练模式下若轮到玩家，则自动撤销两步(玩家+对方)"""
        self._stop_engine_thread()

        is_vs_bot = self.modes.mode in (GameMode.VS_ENGINE, GameMode.VS_MAID_LLM)
        player_turn = (chess.BLACK if self.modes.player_side == "black" else chess.WHITE)
        if is_vs_bot and self.board_state.turn == player_turn and len(self.board_state.board.move_stack) >= 2:
            # 撤销对方步与玩家步
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
            # 引擎根据评估决定是否接受 (复用共享引擎进程, 避免重复拉起开销)
            try:
                def _analyse(client):
                    if self.modes.use_elo and self.modes.target_elo is not None:
                        client.set_elo(self.modes.target_elo)
                    else:
                        client.set_skill_level(self.modes.engine_skill)
                    return client.get_state(self.board_state.get_fen(), state_type="analyse", depth=8)

                state = shared_engine.call(_analyse)
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
        """使在途的引擎思考失效。

        不再使用 terminate() 强杀线程 (存在共享引擎锁悬挂与 UCI 协议失步风险),
        改为自增代际号: 仍在运行的后台线程算完后其结果会因代际不匹配而被丢弃;
        同时置位 cancel_event, 让 LLM HTTP 读取循环立即中止, 不再空烧 Token。
        """
        cancel_event = getattr(self, "_engine_cancel_event", None)
        if cancel_event is not None:
            cancel_event.set()
            self._engine_cancel_event = None
        if self._engine_thread is not None:
            self._engine_generation += 1
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
        text = f"当前行动: {turn_str} [ 被将军 Check! ]" if in_check else f"当前行动: {turn_str}"
        self.status_changed.emit(text, in_check)

    def _apply_mode_headers(self):
        white_name, black_name = self.modes.player_names()
        self.board_state.custom_headers["White"] = white_name
        self.board_state.custom_headers["Black"] = black_name

    def _finalize_game(self, status: dict, override_result: Optional[str] = None):
        """终局处理: 补全对局头并以 'PGN + LLM 总结' 格式归档到历史棋局库

        归档 (含可能耗时的 LLM 复盘网络请求) 在后台守护线程执行, 不阻塞 UI。
        """
        self._stop_engine_thread()
        self._apply_mode_headers()
        status = dict(status)
        result_str = override_result or status.get("result", "*")

        if not self._finalized:
            self._finalized = True

            # 先在主线程内同步取快照与 PGN, 避免后台线程与后续棋局变更竞态
            pgn_to_save = self.board_state.export_pgn(override_result=result_str)
            snapshot = self.get_snapshot()
            provider = self._llm_summary_provider

            def _do_save():
                llm_summary = None
                if provider:
                    try:
                        llm_summary = provider(snapshot, result_str)
                    except TypeError:
                        # 兼容旧签名 provider(snapshot)
                        try:
                            llm_summary = provider(snapshot)
                        except Exception:
                            llm_summary = None
                    except Exception as e:
                        logger.warning("LLM 终局总结生成失败: %s", e, exc_info=True)
                        llm_summary = None
                if not llm_summary:
                    llm_summary = f"对局结束，结果为 {result_str}。终局原因: {status.get('reason', '')}"
                try:
                    self.history_store.save_game(
                        pgn_text=pgn_to_save,
                        result=result_str,
                        llm_summary=llm_summary,
                    )
                except Exception as e:
                    logger.error("棋局归档失败: %s", e, exc_info=True)

            # 后台守护线程落盘: LLM 总结为网络请求, 最长可达数十秒, 绝不能卡住界面
            threading.Thread(target=_do_save, daemon=True, name="game-archive").start()

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

    def import_fen(self, fen: str) -> bool:
        """从 FEN 字符串加载棋局"""
        self._stop_engine_thread()
        try:
            chess.Board(fen.strip())  # 仅用于合法性校验, 非法 FEN 会抛异常
            self.board_state.reset(fen.strip())
            self.history.clear()
            self._finalized = False
            self.position_changed.emit(self.board_state.last_move)
            self.history_changed.emit([])
            self._emit_status()
            status = self.board_state.get_game_status()
            if status["is_over"]:
                self._finalize_game(status)
            else:
                self._check_engine_turn()
            return True
        except Exception:
            return False

    def import_game(self, text: str) -> bool:
        """智能解析并导入 PGN 或 FEN 文本"""
        text = text.strip()
        if not text:
            return False
        # 优先尝试 FEN (以FEN典型格式或单行多段判定)
        tokens = text.split()
        if len(tokens) >= 4 and "/" in tokens[0] and (len(tokens[0].split("/")) == 8):
            if self.import_fen(text):
                return True
        # 尝试 PGN
        if self.import_pgn(text):
            return True
        # 若仍未成功，再尝试作为 FEN 解析
        return self.import_fen(text)

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

    def set_player_side(self, side: str):
        """设置玩家执棋方 ("white" / "black")"""
        self._stop_engine_thread()
        self.modes.player_side = side
        self._apply_mode_headers()
        self._check_engine_turn()

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
            player_side=self.modes.player_side,
        )

    def _agent_query_opening(self, fen: Optional[str] = None, limit: int = 5, *, base_fen: str = "") -> Dict[str, Any]:
        """开局库查询候选走法及权重 (fen 缺省时使用请求构建期冻结的快照 FEN, 不读实时棋盘)"""
        fen_to_query = fen or base_fen or self.board_state.get_fen()
        return self.history_store.query_database(category="opening", fen=fen_to_query, limit=limit)

    def _agent_query_history(self, limit: int = 5, filter_useless: bool = True, query: Optional[str] = None) -> Dict[str, Any]:
        """历史对局查询与归档检索 (可按关键词检索相似历史棋局)"""
        kwargs: Dict[str, Any] = {"limit": limit, "filter_useless": filter_useless}
        if query:
            kwargs["query"] = query
        return self.history_store.query_database(category="history", **kwargs)

    def _agent_read_database(self, category: str = "opening", params: Optional[Dict[str, Any]] = None, *, base_fen: str = "") -> Any:
        """为 LLM 提供的数据库读取统一入口 (支持 opening 与 history)"""
        params = dict(params or {})
        if category == "opening" and "fen" not in params:
            params["fen"] = base_fen or self.board_state.get_fen()
        return self.history_store.query_database(category=category, **params)

    def _agent_read_engine_state(self, state_type: str = "best_move", params: Optional[Dict[str, Any]] = None, *, base_fen: str = "") -> Any:
        """为 LLM 提供的引擎状态读取工具 (支持 best_move / analyse / eval)

        经共享引擎进程执行; 局面 FEN 优先取调用参数, 缺省回退到请求构建期冻结的
        快照 FEN (而非实时棋盘), 保证后台线程不与 UI 写路径竞态。
        引擎缺失或异常时返回 available=False 的降级字典, 保证 LLM 主链路不受影响。
        """
        params = dict(params or {})
        fen = params.pop("fen", None) or base_fen or self.board_state.get_fen()

        def _read(client):
            if self.modes.use_elo and self.modes.target_elo is not None:
                client.set_elo(self.modes.target_elo)
            else:
                client.set_skill_level(self.modes.engine_skill)
            return client.get_state(fen=fen, state_type=state_type, **params)

        try:
            return shared_engine.call(_read)
        except Exception as e:
            logger.warning("Agent 引擎读取失败 (%s): %s", state_type, e)
            return {"available": False, "error": str(e)}

    def _agent_web_search(self, query: str) -> str:
        """为 LLM 提供的轻量联网搜索工具 (支持配置持久化 Search API 接口, 兼容无 key / 默认免 key 模式)"""
        # 优先读取持久化配置中的自定义 search API 配置 (由 MainWindow 注入)
        api_url = (self.search_api_url or "").strip()
        api_key = (self.search_api_key or "").strip()

        # 1. 若配置了自定义搜索 API (例如 Tavily / Serper / 自建搜索代理)
        if api_url:
            try:
                headers = {"User-Agent": "ChessMaidBot/2.0", "Content-Type": "application/json"}
                # 密钥仅通过单一 Authorization 头下发, 且仅对 https 端点发送, 防止明网泄露
                if api_key and api_url.lower().startswith("https://"):
                    headers["Authorization"] = f"Bearer {api_key}"

                payload = json.dumps({"query": query, "q": query}).encode("utf-8")
                req = urllib.request.Request(api_url, data=payload, headers=headers)
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    # 兼容多种格式返回
                    if isinstance(data, dict):
                        if "results" in data and isinstance(data["results"], list) and data["results"]:
                            snippets = [str(r.get("content") or r.get("snippet") or r.get("title", "")) for r in data["results"][:3]]
                            return f"搜索结果: {' | '.join(filter(bool, snippets))}"[:1200]
                        if "abstract" in data:
                            return f"搜索结果: {data['abstract']}"[:1200]
                        if "answer" in data:
                            return f"搜索结果: {data['answer']}"[:1200]
                    return f"搜索结果: {json.dumps(data, ensure_ascii=False)[:300]}"
            except Exception as e:
                # 自定义接口出错时自动降级到 DuckDuckGo / Wikipedia 免 key 开放接口
                logger.info("自定义搜索接口失败, 降级开放搜索: %s", e)

        # 2. 默认免 API Key 开放搜索服务 (DuckDuckGo Instant Answer)
        try:
            url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
            req = urllib.request.Request(url, headers={"User-Agent": "ChessMaidBot/2.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            abstract = data.get("AbstractText", "")
            if abstract:
                return f"搜索结果: {abstract}"[:1200]
            related = data.get("RelatedTopics", [])
            if related and isinstance(related[0], dict) and "Text" in related[0]:
                return f"搜索结果: {related[0]['Text']}"[:1200]
            return f"未检索到关于 '{query}' 的直接摘要信息。"
        except Exception as e:
            return f"联网搜索请求失败: {e}"

    def evaluate_game_moves_quality(self, depth: int = 10, records: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """全盘评估走法质量 (Coach Mode):
        计算每步棋的胜率/评估分落差并打标 (Best, Excellent, Good, Inaccuracy, Mistake, Blunder)

        线程安全: 传入 records (深拷贝) 时在副本上评估且不广播信号,
        供后台归档线程调用而不与 UI 线程读写竞态; 缺省在主线程直接评估实时记录。
        """
        source_records = records if records is not None else self.history.records
        emit_changes = records is None
        evaluated_steps = []
        board = chess.Board()
        prev_eval = 0.0  # 初始白方均势分 cp

        def _analyse(client, fen_str):
            return client.get_state(fen_str, state_type="analyse", depth=depth, multipv=1)

        # 遍历每一步走法
        for rec in source_records:
            # 1. 白方着法评估
            if rec.white_san and rec.white_san != "...":
                try:
                    move = board.parse_san(rec.white_san)
                    board.push(move)
                    fen_after = board.fen()
                    rec.fen_after_white = fen_after
                    
                    state = shared_engine.call(lambda c: _analyse(c, fen_after))
                    cp = 0
                    if state.get("analysis") and state["analysis"][0].get("score_cp") is not None:
                        cp = state["analysis"][0]["score_cp"]
                        # Stockfish 的 cp 评估始终针对当前轮到方，将其统一转换为白方视角评估
                        current_eval_white = cp if board.turn == chess.WHITE else -cp
                    else:
                        current_eval_white = prev_eval
                    
                    delta = current_eval_white - prev_eval  # 白方走棋收益
                    prev_eval = current_eval_white
                    
                    if delta >= 0:
                        q = "Best"
                    elif delta >= -30:
                        q = "Excellent"
                    elif delta >= -80:
                        q = "Good"
                    elif delta >= -180:
                        q = "Inaccuracy"
                    elif delta >= -350:
                        q = "Mistake"
                    else:
                        q = "Blunder"
                    rec.white_quality = q
                    evaluated_steps.append({
                        "ply": rec.move_number * 2 - 1,
                        "move": rec.white_san,
                        "turn": "White",
                        "quality": q,
                        "delta_cp": round(delta, 1),
                        "eval_white": round(current_eval_white, 1)
                    })
                    # 释放 CPU 与引擎锁片刻，避免霸占引擎互斥锁导致前台走棋排队阻塞
                    time.sleep(0.005)
                except Exception:
                    pass

            # 2. 黑方着法评估
            if rec.black_san:
                try:
                    move = board.parse_san(rec.black_san)
                    board.push(move)
                    fen_after = board.fen()
                    rec.fen_after_black = fen_after
                    
                    state = shared_engine.call(lambda c: _analyse(c, fen_after))
                    if state.get("analysis") and state["analysis"][0].get("score_cp") is not None:
                        cp = state["analysis"][0]["score_cp"]
                        current_eval_white = cp if board.turn == chess.WHITE else -cp
                    else:
                        current_eval_white = prev_eval
                    
                    delta = prev_eval - current_eval_white  # 黑方走棋收益 (白方越低黑方越赚)
                    prev_eval = current_eval_white
                    
                    if delta >= 0:
                        q = "Best"
                    elif delta >= -30:
                        q = "Excellent"
                    elif delta >= -80:
                        q = "Good"
                    elif delta >= -180:
                        q = "Inaccuracy"
                    elif delta >= -350:
                        q = "Mistake"
                    else:
                        q = "Blunder"
                    rec.black_quality = q
                    evaluated_steps.append({
                        "ply": rec.move_number * 2,
                        "move": rec.black_san,
                        "turn": "Black",
                        "quality": q,
                        "delta_cp": round(delta, 1),
                        "eval_white": round(current_eval_white, 1)
                    })
                    # 释放 CPU 与引擎锁片刻，避免霸占引擎互斥锁导致前台走棋排队阻塞
                    time.sleep(0.005)
                except Exception:
                    pass

        if emit_changes:
            self.history_changed.emit(self.history.records)
        return evaluated_steps

    def _agent_request_undo(self, reason: str = "局势不利") -> bool:
        """与LLM对弈模式下，LLM发送悔棋请求"""
        if self.modes.mode == GameMode.VS_MAID_LLM:
            self.undo_requested_by_llm.emit(reason)
            return True
        return False

    def build_agent_request(
        self,
        user_message: str,
        persona_prompt: str,
        dialog_history: Optional[List[dict]] = None,
        player_profile_summary: Optional[str] = None,
    ) -> AgentRequest:
        """构建标准 Agent 请求。

        线程安全: 快照在构建时冻结; 所有工具闭包优先使用该快照 FEN,
        后台线程调用工具时不再读取实时棋盘状态 (消除与 UI 写路径的竞态)。
        """
        snapshot = self.get_snapshot()
        frozen_fen = snapshot.fen
        tools = AgentTools(
            query_opening=lambda fen=None, limit=5: self._agent_query_opening(fen, limit, base_fen=frozen_fen),
            query_history=self._agent_query_history,
            read_database=lambda category="opening", params=None: self._agent_read_database(category, params, base_fen=frozen_fen),
            read_engine_state=lambda state_type="best_move", params=None: self._agent_read_engine_state(state_type, params, base_fen=frozen_fen),
            web_search=self._agent_web_search,
            request_undo=self._agent_request_undo,
        )
        return AgentRequest(
            user_message=user_message,
            persona_prompt=persona_prompt,
            snapshot=snapshot,
            dialog_history=list(dialog_history or []),
            tools=tools,
            game_mode=self.modes.mode.value,
            player_profile_summary=player_profile_summary,
        )

