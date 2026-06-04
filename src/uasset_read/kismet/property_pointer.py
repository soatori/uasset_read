"""
Kismet 属性指针 — FFieldPath + FKismetPropertyPointer。

对应 UE 引擎中的 FFieldPath 和 FKismetPropertyPointer 结构体，
用于在 Kismet 字节码中引用对象属性。

UE4.25+ 引入 bNew 标志位：True 时使用 FFieldPath 路径引用，
False 时使用 legacy FPackageIndex 单步引用。
简化实现：始终读取 FFieldPath 路径（UE5 默认行为）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.serializers.object_resources import PackageIndex


@dataclass
class FFieldPath:
    """
    UE5 FFieldPath — 属性路径引用。

    Path 存储从 FName 名称表解析的路径段列表。
    ResolvedOwner 为 UE5 新增字段，存储路径解析的所有者 PackageIndex。
    """

    Path: list[str] = field(default_factory=list)
    ResolvedOwner: Optional[PackageIndex] = field(default=None)

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: list[str]) -> FFieldPath:
        """
        从 FArchive 反序列化 FFieldPath。

        读取逻辑：
        1. 读取 u32 数组长度（Path 段数）
        2. 循环读取每个 FName 索引（u32），查 name_map 解析为字符串
        3. 如果第一个元素是 "None"，清空 Path（表示空路径）
        4. 检查版本/引擎状态读取可选的 ResolvedOwner
        """
        count = archive.read_u32()

        path: list[str] = []
        for _ in range(count):
            name_index = archive.read_u32()
            path.append(archive.resolve_fname(name_index))

        # 如果第一个元素是 "None"，表示空路径
        if path and path[0] == "None":
            path.clear()

        return cls(Path=path)


@dataclass
class FKismetPropertyPointer:
    """
    FKismetPropertyPointer — Kismet 字节码中的属性引用指针。

    bNew 标志位区分两种引用模式：
    - True (UE4.25+): 使用 FFieldPath 多段路径引用
    - False (legacy): 使用 FPackageIndex 单步引用

    简化实现：始终使用 New (FFieldPath) 路径。
    """

    bNew: bool = True
    Old: Optional[PackageIndex] = field(default=None)
    New: Optional[FFieldPath] = field(default=None)

    @classmethod
    def from_archive(
        cls, archive: FArchive, name_map: list[str]
    ) -> FKismetPropertyPointer:
        """
        从 FArchive 反序列化 FKismetPropertyPointer。

        简化：读取 bNew 标志后，始终使用 New (FFieldPath) 路径。
        完整的 legacy Old 路径支持留待后续实现。
        """
        b_new = archive.read_bool()

        if b_new:
            new_path = FFieldPath.from_archive(archive, name_map)
            return cls(bNew=True, New=new_path)
        else:
            # Legacy path: read FPackageIndex (single int32)
            old_index = PackageIndex(archive.read_i32())
            return cls(bNew=False, Old=old_index)

    def __str__(self) -> str:
        """返回属性的路径字符串表示。"""
        if self.New and self.New.Path:
            return self.New.Path[0]
        if self.Old is not None:
            return str(self.Old.index)
        return "None"
