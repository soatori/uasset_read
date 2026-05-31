"""ObjectTypeRegistry — UObject 类型注册表

等价实现 ObjectTypeRegistry.cs
"""
from __future__ import annotations
from typing import Dict, Type
import logging

from uasset_read.objects.uobject import UObject

logger = logging.getLogger(__name__)


class ObjectTypeRegistry:
    """UObject 类型注册表

    通过装饰器注册 UObject 子类，支持按名称查找和蓝图生成类后缀剥离。
    """

    def __init__(self) -> None:
        self._classes: Dict[str, Type[UObject]] = {}

    @property
    def classes(self) -> Dict[str, Type[UObject]]:
        """已注册的类型映射（只读）"""
        return dict(self._classes)

    def register(self, class_name: str):
        """装饰器：注册 UObject 子类

        Usage:
            @registry.register("StaticMesh")
            class UStaticMesh(UObject):
                pass
        """
        def decorator(cls: Type[UObject]) -> Type[UObject]:
            self._classes[class_name] = cls
            logger.debug("Registered UObject type: %s", class_name)
            return cls
        return decorator

    def get_class(self, serialized_name: str) -> Type[UObject]:
        """根据序列化名称获取类

        如果名称以 '_C' 结尾（蓝图生成类），会尝试剥离后缀再查找。
        找不到时返回 UObject 基类。
        """
        # 直接查找
        if serialized_name in self._classes:
            return self._classes[serialized_name]

        # 尝试剥离 _C 后缀（蓝图生成类）
        if serialized_name.endswith('_C'):
            base_name = serialized_name[:-2]
            if base_name in self._classes:
                return self._classes[base_name]

        # 返回基类
        return UObject

    def has_class(self, class_name: str) -> bool:
        """检查是否已注册指定类型"""
        return class_name in self._classes

    def list_classes(self) -> list[str]:
        """列出所有已注册的类型名称"""
        return list(self._classes.keys())


# 全局注册表实例
global_registry = ObjectTypeRegistry()
