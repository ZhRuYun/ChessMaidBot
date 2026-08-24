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
"""
from pathlib import Path
from typing import Optional, Dict, List

from ..config import (
    ENGINE_PATH,
    STOCKFISH_DEFAULT_SKILL,
    STOCKFISH_DEFAULT_ELO,
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
        import subprocess
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
        """固定深度分析, 返回 [{score_cp, pv}] (multipv 支持推荐走法列表)"""
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
                        score_cp = int(tokens[i + 1])
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
