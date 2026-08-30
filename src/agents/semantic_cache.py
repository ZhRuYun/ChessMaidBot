"""
语义缓存 (模块5 - Agent 扩展)
面向「确定性上下文请求」的双层 LRU + 磁盘持久化结果缓存:
  - 自动教学 / 主动询问类请求仅由 (FEN, 教学开关, 模式) 决定, 同局面重复触发可直接复用回复
  - 显著降低重复 Token 开销; 自由聊天不入缓存
  - 支持内存高速缓存与本地磁盘 JSON 持久化双层设计
纯标准库实现, 无第三方依赖。
"""
import hashlib
import json
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Dict, Any

from ..config import DATA_DIR

logger = logging.getLogger("chessmaid.cache")


class SemanticCache:
    """基于键哈希的 LRU + 磁盘持久化语义缓存 (带命中统计)"""

    def __init__(self, maxsize: int = 128, disk_path: Optional[Path] = None):
        self.maxsize = maxsize
        self.disk_path = disk_path or (DATA_DIR / "semantic_cache.json")
        self._store: "OrderedDict[str, str]" = OrderedDict()
        self.hits = 0
        self.misses = 0
        self._load_from_disk()

    def _load_from_disk(self):
        """启动时从磁盘加载持久化缓存"""
        if self.disk_path.exists():
            try:
                with open(self.disk_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for k, v in list(data.items())[-self.maxsize:]:
                            self._store[k] = v
            except Exception as e:
                logger.debug("读取磁盘语义缓存失败: %s", e)

    def _save_to_disk(self):
        """异步/定时或写入时持久化到磁盘"""
        try:
            self.disk_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.disk_path, "w", encoding="utf-8") as f:
                json.dump(dict(self._store), f, ensure_ascii=False)
        except Exception as e:
            logger.debug("持久化语义缓存失败: %s", e)

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
        self._save_to_disk()

    def clear(self):
        self._store.clear()
        if self.disk_path.exists():
            try:
                self.disk_path.unlink()
            except Exception:
                pass

    def stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._store),
            "maxsize": self.maxsize,
            "hits": self.hits,
            "misses": self.misses,
        }
