"""
Stockfish UCI 引擎客户端 (模块4)
Stockfish 本质是由 stdin/stdout 控制的命令行程序, 本类封装其通信协议,
向其余模块提供 best_move / analyse / set_elo / set_skill_level 等高层接口

使用方法:
    1. 将 Stockfish 可执行文件放置于 engines/ 目录 (路径见 config.ENGINE_PATH)
    2. with StockfishClient() as engine: engine.best_move(fen)

强度调节支持:
    - 官方 Skill Level (0-20)
    - 目标 Elo 评分 (UCI_LimitStrength + UCI_Elo 1320~3190)

性能优化:
    - SharedEngine / shared_engine: 进程级共享引擎客户端池 (懒启动 + 线程互斥),
      避免每次走棋/分析都重新拉起 Stockfish 进程 (NNUE 权重加载耗时数百毫秒)
"""
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, List

from ..config import (
    ENGINE_PATH,
    STOCKFISH_DEFAULT_SKILL,
    STOCKFISH_MIN_ELO,
    STOCKFISH_MAX_ELO,
)


class StockfishError(RuntimeError):
    pass


class StockfishClient:
    def __init__(
        self,
        binary_path: Optional[Path] = None,
        skill_level: int = STOCKFISH_DEFAULT_SKILL,
        target_elo: Optional[int] = None,
    ):
        self.binary_path = Path(binary_path) if binary_path else ENGINE_PATH
        self.skill_level = skill_level
        self.target_elo = target_elo
        self._proc = None

    @property
    def available(self) -> bool:
        return self.binary_path.exists()

    def start(self):
        if self._proc is not None:
            return
        if not self.available:
            raise StockfishError(f"未找到 Stockfish 引擎: {self.binary_path}")
        self._proc = subprocess.Popen(
            [str(self.binary_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._send("uci")
        self._read_until("uciok")
        if self.target_elo is not None:
            self.set_elo(self.target_elo)
        else:
            self.set_skill_level(self.skill_level)

    def _send(self, command: str):
        if self._proc is None or self._proc.stdin is None:
            raise StockfishError("引擎尚未启动")
        self._proc.stdin.write(command + "\n")
        self._proc.stdin.flush()

    def _read_line(self) -> str:
        if self._proc is None or self._proc.stdout is None:
            raise StockfishError("引擎尚未启动")
        line = self._proc.stdout.readline()
        if not line:
            raise StockfishError("引擎输出流已关闭")
        return line.strip()

    def _read_until(self, token: str) -> str:
        while True:
            line = self._read_line()
            if line.startswith(token) or line == token:
                return line

    def set_skill_level(self, skill: int):
        """官方 UCI 选项: Skill Level 0(最弱)-20(最强), 关闭 Elo 限制"""
        self.skill_level = max(0, min(20, skill))
        self.target_elo = None
        if self._proc is not None and self._proc.stdin is not None:
            self._send("setoption name UCI_LimitStrength value false")
            self._send(f"setoption name Skill Level value {self.skill_level}")

    def set_elo(self, elo: int):
        """官方 UCI 参数控制 Stockfish 目标 Elo 等级分 (UCI_LimitStrength + UCI_Elo)"""
        self.target_elo = max(STOCKFISH_MIN_ELO, min(STOCKFISH_MAX_ELO, elo))
        if self._proc is not None and self._proc.stdin is not None:
            self._send("setoption name UCI_LimitStrength value true")
            if self.target_elo < 1320:
                skill = max(0, int((self.target_elo - 500) / (1320 - 500) * 6))
                self._send(f"setoption name Skill Level value {skill}")
                self._send("setoption name UCI_Elo value 1320")
            else:
                self._send(f"setoption name UCI_Elo value {self.target_elo}")

    def _sync(self):
        self._send("isready")
        self._read_until("readyok")

    def best_move(self, fen: str, movetime_ms: int = 1000) -> Optional[str]:
        """返回最佳走法 UCI (如 e2e4), 无合法走法时返回 None"""
        self.start()
        self._send(f"position fen {fen}")
        self._send(f"go movetime {movetime_ms}")
        line = self._read_until("bestmove")
        parts = line.split()
        if len(parts) >= 2 and parts[1] != "(none)":
            return parts[1]
        return None

    def analyse(self, fen: str, depth: int = 15, multipv: int = 1) -> List[Dict[str, object]]:
        """固定深度分析, 返回 [{score_cp, pv}] (支持多PV候选分析)"""
        self.start()
        self._send(f"setoption name MultiPV value {multipv}")
        self._sync()
        self._send(f"position fen {fen}")
        self._send(f"go depth {depth}")

        results: Dict[int, Dict[str, object]] = {}
        while True:
            line = self._read_line()
            if line.startswith("info") and " pv " in line and " score " in line:
                multipv_index = 1
                score_cp = None
                pv: List[str] = []
                tokens = line.split()
                for i, tok in enumerate(tokens):
                    if tok == "multipv" and i + 1 < len(tokens):
                        multipv_index = int(tokens[i + 1])
                    elif tok == "cp" and i + 1 < len(tokens):
                        try:
                            score_cp = int(tokens[i + 1])
                        except ValueError:
                            score_cp = None
                    elif tok == "mate" and i + 1 < len(tokens):
                        try:
                            mate_in = int(tokens[i + 1])
                            # 将死分数转换为超大分值，保留步数距离判定
                            if mate_in > 0:
                                score_cp = 100000 - mate_in * 100
                            elif mate_in < 0:
                                score_cp = -100000 - mate_in * 100
                            else:
                                score_cp = 100000
                        except ValueError:
                            score_cp = None
                    elif tok == "pv":
                        pv = tokens[i + 1:]
                        break
                results[multipv_index] = {"score_cp": score_cp, "pv": pv}
            elif line.startswith("bestmove"):
                break
        return [results[k] for k in sorted(results)]

    def get_state(self, fen: str, state_type: str = "best_move", **kwargs) -> Dict[str, object]:
        """为 Agent 与外部模块提供的统一引擎状态读取接口
        
        Args:
            fen: 待评估的 FEN 局面
            state_type: 读取的引擎状态部分 ("best_move" | "analyse" | "eval")
            **kwargs: 额外参数 (movetime_ms, depth, multipv 等)
            
        Returns:
            引擎状态结果字典
        """
        if not self.available:
            return {"available": False, "error": "Stockfish binary not found"}

        try:
            if state_type == "best_move":
                movetime_ms = kwargs.get("movetime_ms", 500)
                move = self.best_move(fen, movetime_ms=movetime_ms)
                return {"available": True, "state_type": "best_move", "best_move": move}
            elif state_type in ("analyse", "eval"):
                depth = kwargs.get("depth", 12)
                multipv = kwargs.get("multipv", 1)
                analysis = self.analyse(fen, depth=depth, multipv=multipv)
                return {"available": True, "state_type": "analyse", "analysis": analysis}
            else:
                return {"available": True, "state_type": state_type, "error": f"Unknown state_type: {state_type}"}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def quit(self):
        if self._proc is not None:
            try:
                if self._proc.stdin:
                    try:
                        self._send("quit")
                    except Exception:
                        pass
                    self._proc.stdin.close()
                if self._proc.stdout:
                    self._proc.stdout.close()
                self._proc.wait(timeout=1)
            except Exception:
                self._proc.kill()
            finally:
                self._proc = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()
        return False


class SharedEngine:
    """进程级共享 Stockfish 客户端 (懒启动 + 线程安全互斥)

    目的: 复用同一个引擎子进程, 避免「每步棋/每次分析重新拉起进程 + 加载 NNUE」
   带来的数百毫秒级开销。所有调用在互斥锁内串行执行, 保证 UCI 协议不发生交错。

    注意: 使用方严禁在持有锁期间被强制终止 (terminate), 否则锁将永久悬挂;
    应通过「代际 (generation) 丢弃」机制让过期结果自然失效。
    """

    def __init__(self, binary_path: Optional[Path] = None):
        self._lock = threading.Lock()
        self._client: Optional[StockfishClient] = None
        self._binary_path = binary_path

    def call(self, fn):
        """在互斥锁内以已启动的客户端执行 fn(client) 并返回其结果。

        任何异常都会销毁当前客户端, 确保下一次调用从干净状态重新启动。
        """
        with self._lock:
            if self._client is None:
                self._client = StockfishClient(binary_path=self._binary_path)
            try:
                self._client.start()
                return fn(self._client)
            except Exception:
                self._destroy_locked()
                raise

    def reset(self):
        """强制销毁当前客户端 (调用方线程被强停等导致协议失步时使用)"""
        with self._lock:
            self._destroy_locked()

    def _destroy_locked(self):
        if self._client is not None:
            try:
                self._client.quit()
            except Exception:
                pass
            self._client = None


# 全局共享引擎实例: 调度层 (EngineWorker / 求和评估 / Agent 工具) 统一复用
shared_engine = SharedEngine()
