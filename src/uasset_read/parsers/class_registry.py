"""src/uasset_read/parsers/class_registry.py — Class Handler Registry。

参考 CUE4Parse ObjectTypeRegistry 模式：
1. 精确 class handler 查找
2. 父类 handler 查找（后续扩展）
3. generic UObject fallback
4. skip policy 作为最后的 fallback

handler 接口：
- can_handle(class_name) -> bool
- parse(export, archive, context) -> HandlerResult
- fallback_policy -> FallbackPolicy
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.models.properties import PropertyValue

logger = logging.getLogger(__name__)


class FallbackPolicy(str, Enum):
    """当 handler 无法处理时的 fallback 策略。"""
    GENERIC_UOBJECT = "generic_uobject"
    SKIP = "skip"
    RAISE = "raise"
    PROPERTY_FALLBACK = "property_fallback"


@dataclass
class HandlerResult:
    """Class handler 的解析结果。"""
    success: bool
    properties: List["PropertyValue"] = field(default_factory=list)
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    fallback_policy: FallbackPolicy = FallbackPolicy.GENERIC_UOBJECT


class ClassHandler(ABC):
    """Class handler 抽象基类。"""

    @abstractmethod
    def can_handle(self, class_name: str) -> bool:
        """判断此 handler 是否能处理给定 class_name。"""
        ...

    @property
    @abstractmethod
    def handler_name(self) -> str:
        """handler 名称（用于日志和诊断）。"""
        ...

    @property
    def fallback_policy(self) -> FallbackPolicy:
        """当 handler 解析失败时的 fallback 策略。"""
        return FallbackPolicy.GENERIC_UOBJECT

    @abstractmethod
    def parse(
        self,
        export: "ObjectExport",
        archive: "FArchive",
        context: Optional[Any] = None,
    ) -> HandlerResult:
        """解析 export 的属性数据。"""
        ...


class ClassHandlerRegistry:
    """Class handler 注册表。"""

    def __init__(self) -> None:
        self._handlers: List[ClassHandler] = []
        self._cache: Dict[str, Optional[ClassHandler]] = {}

    def register(self, handler: ClassHandler) -> None:
        """注册一个 class handler。"""
        self._handlers.append(handler)
        self._cache.clear()

    def find_handler(self, class_name: str) -> Optional[ClassHandler]:
        """查找能处理给定 class_name 的 handler。"""
        if class_name in self._cache:
            return self._cache[class_name]

        for handler in self._handlers:
            if handler.can_handle(class_name):
                self._cache[class_name] = handler
                return handler

        self._cache[class_name] = None
        return None

    def get_registered_handlers(self) -> List[ClassHandler]:
        """返回所有已注册的 handler。"""
        return list(self._handlers)

    def clear(self) -> None:
        """清空所有注册和缓存。"""
        self._handlers.clear()
        self._cache.clear()


# 全局默认 registry 实例
_default_registry: Optional[ClassHandlerRegistry] = None


def get_class_registry() -> ClassHandlerRegistry:
    """获取全局默认 class handler registry。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ClassHandlerRegistry()
    return _default_registry


def reset_class_registry() -> None:
    """重置全局默认 registry（测试用）。"""
    global _default_registry
    _default_registry = None
