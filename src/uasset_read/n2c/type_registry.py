"""K2Node 类型注册表 — 单例模式 + 继承回退 + 缓存。

将 UE K2Node class_name 解析为 N2CNodeType 语义类型枚举。
支持精确匹配和继承链回退查找。

Phase 68 Wave 2 输出。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Optional

from uasset_read.n2c.type_data import K2NODE_ENUM_NAMES, K2NODE_INHERITANCE

if TYPE_CHECKING:
    from uasset_read.n2c.node_types import N2CNodeType

logger = logging.getLogger(__name__)


class N2CNodeTypeRegistry:
    """K2Node 类名 -> 语义类型注册表（单例）。

    提供 class_name 到 N2CNodeType 的解析服务：
    - 精确匹配：K2Node_CallFunction -> CallFunction
    - 继承回退：沿 K2NODE_INHERITANCE 向上查找
    - 缓存优化：_resolve_cache 避免重复查找
    - Unknown fallback：未知类型返回 Unknown

    使用方式：
        registry = N2CNodeTypeRegistry.get_instance()
        node_type = registry.resolve("K2Node_CallFunction")
    """

    _instance: Optional[N2CNodeTypeRegistry] = None

    def __init__(self) -> None:
        self._type_map: Dict[str, N2CNodeType] = {}
        self._inheritance_map: Dict[str, str] = K2NODE_INHERITANCE
        self._resolve_cache: Dict[str, N2CNodeType] = {}
        self._initialized = False

    @classmethod
    def get_instance(cls) -> N2CNodeTypeRegistry:
        """获取单例实例（延迟创建）。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例（测试用）。"""
        cls._instance = None

    def _ensure_initialized(self) -> None:
        """延迟填充 _type_map，避免导入循环。

        首次 resolve() 时触发，将 K2NODE_ENUM_NAMES 映射为
        N2CNodeType 枚举值存入 _type_map。
        """
        if self._initialized:
            return
        from uasset_read.n2c.node_types import N2CNodeType

        for class_name, enum_name in K2NODE_ENUM_NAMES.items():
            try:
                self._type_map[class_name] = N2CNodeType[enum_name]
            except KeyError:
                logger.warning("No enum member '%s' for class '%s'", enum_name, class_name)
        self._initialized = True

    def resolve(self, class_name: str) -> N2CNodeType:
        """解析 class_name 到 N2CNodeType，支持继承回退。

        查找顺序：
        1. 精确匹配 _type_map[class_name]
        2. 缓存命中 _resolve_cache[class_name]
        3. 继承链查找：沿 _inheritance_map 向上查找父类
        4. Unknown fallback

        Args:
            class_name: K2Node 类名（如 "K2Node_CallFunction"）

        Returns:
            对应的 N2CNodeType 枚举值
        """
        self._ensure_initialized()

        # 精确匹配
        if class_name in self._type_map:
            return self._type_map[class_name]

        # 缓存命中
        if class_name in self._resolve_cache:
            return self._resolve_cache[class_name]

        # 继承链查找
        from uasset_read.n2c.node_types import N2CNodeType

        current = class_name
        visited: set[str] = set()
        max_depth = 10

        while current in self._inheritance_map and len(visited) < max_depth:
            if current in visited:
                break  # 循环保护
            visited.add(current)
            parent = self._inheritance_map[current]
            if parent in self._type_map:
                result = self._type_map[parent]
                self._resolve_cache[class_name] = result
                return result
            current = parent

        # Unknown fallback
        self._resolve_cache[class_name] = N2CNodeType.Unknown
        return N2CNodeType.Unknown

    def get_registered_types(self) -> list[str]:
        """返回所有已注册的 class_name 列表（诊断用）。"""
        self._ensure_initialized()
        return sorted(self._type_map.keys())
