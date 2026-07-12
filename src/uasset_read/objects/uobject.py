from __future__ import annotations

"""UObject 基类 — 所有 UE 资产类型的根"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


@dataclass
class UObject:
    """UObject 基类

    等价实现 UObject.cs
    """
    name: str = ""
    flags: int = 0
    outer: Optional[UObject] = None

    # 属性存储
    properties: Dict[str, Any] = field(default_factory=dict)

    def get_property(self, name: str, default: Any = None) -> Any:
        """获取属性值"""
        return self.properties.get(name, default)

    def set_property(self, name: str, value: Any) -> None:
        """设置属性值"""
        self.properties[name] = value

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """反序列化对象数据

        Args:
            archive: FArchive 实例
            offset: 数据偏移
            size: 数据大小
        """
        # 基类默认实现：读取属性列表
        # 子类可覆盖以实现特定反序列化逻辑
        pass
