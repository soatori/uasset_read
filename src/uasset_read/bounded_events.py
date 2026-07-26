"""有界事件缓冲区 — 保留首段、尾段、去重计数。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(eq=False)
class BoundedEventBuffer:
    """有界事件缓冲区 — 保留首段、尾段、去重计数。

    用于收集 diagnostics、warnings、errors 和 HexView 条目。
    当达到条目数或字节上限时，新条目会被丢弃并计数。

    Attributes:
        max_entries: 最大条目数
        max_bytes: 最大字节数（基于 str(entry) 长度）
    """

    max_entries: int = 1000
    max_bytes: int = 1024 * 1024  # 1 MB

    def __post_init__(self) -> None:
        """初始化内部状态。"""
        self._entries: list[Any] = []
        self._total_bytes: int = 0
        self._dropped_count: int = 0

    def append(self, entry: Any) -> bool:
        """添加条目，超限时返回 False。

        Args:
            entry: 任意条目（通过 str(entry) 计算大小）

        Returns:
            True 表示添加成功，False 表示已超限被丢弃
        """
        entry_size = len(str(entry))
        if len(self._entries) >= self.max_entries or self._total_bytes + entry_size > self.max_bytes:
            self._dropped_count += 1
            return False
        self._entries.append(entry)
        self._total_bytes += entry_size
        return True

    @property
    def entries(self) -> list[Any]:
        """返回当前条目列表（副本）。"""
        return list(self._entries)

    @property
    def dropped_count(self) -> int:
        """返回被丢弃的条目总数。"""
        return self._dropped_count

    @property
    def total_bytes(self) -> int:
        """返回当前已用字节数。"""
        return self._total_bytes

    @property
    def count(self) -> int:
        """返回当前条目数。"""
        return len(self._entries)

    def clear(self) -> None:
        """清空缓冲区。"""
        self._entries.clear()
        self._total_bytes = 0
        self._dropped_count = 0

    def __len__(self) -> int:
        """返回当前条目数。"""
        return len(self._entries)

    def __bool__(self) -> bool:
        """缓冲区非空时返回 True。"""
        return len(self._entries) > 0


@dataclass(eq=False)
class BoundedSet:
    """有界集合 — 超限后停止添加并计数丢弃次数。

    用于名称警告去重等场景，防止损坏文件导致集合无限增长。

    Attributes:
        max_size: 最大元素数
    """

    max_size: int = 10000

    def __post_init__(self) -> None:
        """初始化内部状态。"""
        self._set: set[int] = set()
        self._dropped_count: int = 0

    def add(self, value: int) -> bool:
        """添加元素，超限时返回 False。

        Args:
            value: 要添加的整数值

        Returns:
            True 表示添加成功，False 表示已超限被丢弃
        """
        if value in self._set:
            return True
        if len(self._set) >= self.max_size:
            self._dropped_count += 1
            return False
        self._set.add(value)
        return True

    def __contains__(self, value: int) -> bool:
        """检查元素是否在集合中。"""
        return value in self._set

    def __len__(self) -> int:
        """返回当前元素数。"""
        return len(self._set)

    @property
    def dropped_count(self) -> int:
        """返回被丢弃的元素总数。"""
        return self._dropped_count

    def clear(self) -> None:
        """清空集合。"""
        self._set.clear()
        self._dropped_count = 0
