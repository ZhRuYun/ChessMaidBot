"""
在线网络双人对战极简服务与客户端模块 (模块2/模块1 扩展)
采用轻量 HTTP / JSON 轮询机制，实现零外部依赖的局域网/互联网对战原型。
"""
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.parse
from typing import Optional
from PySide6.QtCore import QObject, Signal, QTimer


class OnlineGameRoomState:
    """服务端单房间对局状态"""
    def __init__(self):
        self.lock = threading.Lock()
        self.moves = []       # List of UCI moves
        self.fen = ""
        self.chat = []
        self.white_joined = False
        self.black_joined = False
        self.game_over = False
        self.game_result = "*"


class OnlineServerHandler(BaseHTTPRequestHandler):
    room_state = OnlineGameRoomState()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/status":
            with self.room_state.lock:
                data = {
                    "moves": self.room_state.moves,
                    "fen": self.room_state.fen,
                    "white_joined": self.room_state.white_joined,
                    "black_joined": self.room_state.black_joined,
                    "game_over": self.room_state.game_over,
                    "game_result": self.room_state.game_result,
                }
            self._send_json(200, data)
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            req_data = json.loads(body)
        except Exception:
            req_data = {}

        if parsed.path == "/join":
            side = req_data.get("side", "auto")
            with self.room_state.lock:
                if side == "white" and not self.room_state.white_joined:
                    self.room_state.white_joined = True
                    assigned = "white"
                elif side == "black" and not self.room_state.black_joined:
                    self.room_state.black_joined = True
                    assigned = "black"
                elif not self.room_state.white_joined:
                    self.room_state.white_joined = True
                    assigned = "white"
                elif not self.room_state.black_joined:
                    self.room_state.black_joined = True
                    assigned = "black"
                else:
                    assigned = "spectator"
            self._send_json(200, {"status": "ok", "assigned_side": assigned})

        elif parsed.path == "/move":
            move_uci = req_data.get("move")
            fen = req_data.get("fen", "")
            with self.room_state.lock:
                if move_uci:
                    self.room_state.moves.append(move_uci)
                if fen:
                    self.room_state.fen = fen
            self._send_json(200, {"status": "ok", "move_count": len(self.room_state.moves)})

        elif parsed.path == "/reset":
            with self.room_state.lock:
                self.room_state.moves.clear()
                self.room_state.fen = ""
                self.room_state.game_over = False
                self.room_state.game_result = "*"
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "unknown action"})

    def _send_json(self, code: int, data: dict):
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def log_message(self, format, *args):
        # 静默日志，避免刷屏
        pass


class OnlineMatchClient(QObject):
    """网络对战客户端 (基于 QTimer 轮询服务端状态)"""
    opponent_moved = Signal(str)  # 接收到对方走法 (UCI)
    status_updated = Signal(dict)
    connection_lost = Signal(str)

    def __init__(self, host: str = "127.0.0.1", port: int = 8765, parent=None):
        super().__init__(parent)
        self.base_url = f"http://{host}:{port}"
        self.my_side = "white"  # "white" 或 "black"
        self._synced_move_count = 0
        self._timer = QTimer(self)
        self._timer.setInterval(800)  # 800ms 轮询一次
        self._timer.timeout.connect(self._poll_status)

    def start(self, my_side: str = "white"):
        self.my_side = my_side
        self._synced_move_count = 0
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def send_move(self, uci_move: str, fen: str):
        def _post():
            try:
                data = json.dumps({"move": uci_move, "fen": fen}).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.base_url}/move", data=data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=3):
                    pass
            except Exception:
                pass
        threading.Thread(target=_post, daemon=True).start()
        self._synced_move_count += 1

    def send_reset(self):
        def _post():
            try:
                data = b"{}"
                req = urllib.request.Request(
                    f"{self.base_url}/reset", data=data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=3):
                    pass
            except Exception:
                pass
        threading.Thread(target=_post, daemon=True).start()
        self._synced_move_count = 0

    def _poll_status(self):
        def _get():
            try:
                req = urllib.request.Request(f"{self.base_url}/status")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    body = resp.read().decode("utf-8")
                    data = json.loads(body)
                    return data
            except Exception:
                return None

        res = _get()
        if res is None:
            return

        moves = res.get("moves", [])
        if len(moves) > self._synced_move_count:
            # 有新走法
            for m in moves[self._synced_move_count:]:
                self.opponent_moved.emit(m)
            self._synced_move_count = len(moves)


class EmbeddedOnlineServer:
    """内置极简 HTTP 对战房间服务器"""
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self.httpd is not None:
            return
        OnlineServerHandler.room_state = OnlineGameRoomState()
        self.httpd = HTTPServer((self.host, self.port), OnlineServerHandler)
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            self._thread = None
