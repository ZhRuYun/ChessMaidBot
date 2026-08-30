"""
语义缓存 (模块5 - Agent 扩展)
面向「确定性上下文请求」的 LRU 结果缓存:
  - 自动教学 / 主动询问类请求仅由 (FEN, 教学开关, 模式) 决定, 同局面重复触发可直接复用回复
  - 显著降低重复 Token 开销; 自由聊天不入缓存
纯标准库实现, 无第三方依赖。
"""
import hashlib
from collections import OrderedDict
from typing import Optional, Dict, Any


class SemanticCache:
    """基于键哈希的 LRU 语义缓存 (带命中统计)"""

    def __init__(self, maxsize: int = 128):
        self.maxsize = maxsize
        self._store: "OrderedDict[str, str]" = OrderedDict()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(*parts: Any) -> str:
        """由若干上下文部件生成稳定缓存键"""
        raw = "|".join(str(p) for p in parts)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[str]:
        if key in self._store:
            self._store.move_to_end(key)
            self.hits += 1
            return self._store[key]
        self.misses += 1
        return None

    def put(self, key: str, value: str):
        if not value:
            return
        self._store[key] = value
        self._store.move_to_end(key)
        while len(self._store) > self.maxsize:
            self._store.popitem(last=False)

    def clear(self):
        self._store.clear()

    def stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._store),
            "maxsize": self.maxsize,
            "hits": self.hits,
            "misses": self.misses,
        }
