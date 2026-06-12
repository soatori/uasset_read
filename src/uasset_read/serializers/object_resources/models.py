"""Object Resources 数据模型 — PackageIndex, ObjectImport, ObjectExport, ResolvedPackageIndex。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class PackageIndex:
    """FPackageIndex 编码。

    UE 源码基准：ObjectResource.h FPackageIndex
    - Index > 0: Export 引用，实际下标 = Index - 1
    - Index < 0: Import 引用，实际下标 = -Index - 1
    - Index = 0: Null 引用
    """
    index: int

    @property
    def is_import(self) -> bool:
        return self.index < 0

    @property
    def is_export(self) -> bool:
        return self.index > 0

    @property
    def is_null(self) -> bool:
        return self.index == 0

    @property
    def resolved_type(self) -> str:
        """解析类型："null" | "import" | "export\""""
        if self.is_null:
            return "null"
        elif self.is_import:
            return "import"
        else:
            return "export"

    @property
    def import_index(self) -> int | None:
        """Import 数组下标（仅当 is_import 时有效）"""
        if not self.is_import:
            return None
        return -self.index - 1

    @property
    def export_index(self) -> int | None:
        """Export 数组下标（仅当 is_export 时有效）"""
        if not self.is_export:
            return None
        return self.index - 1

    def to_import_index(self) -> int:
        """向后兼容方法：返回 Import 数组下标"""
        return -self.index - 1

    def to_export_index(self) -> int:
        """向后兼容方法：返回 Export 数组下标"""
        return self.index - 1

    def resolve(
        self,
        import_map: list["ObjectImport"],
        export_map: list["ObjectExport"]
    ) -> "ResolvedPackageIndex":
        """解析为目标条目信息

        Args:
            import_map: Import 表（FObjectImport 列表）
            export_map: Export 表（FObjectExport 列表）

        Returns:
            ResolvedPackageIndex: 包含名称和完整路径的解析结果
        """
        if self.is_null:
            return ResolvedPackageIndex(
                name="None",
                full_path="None",
                ref_type="null",
                target_entry=None
            )
        elif self.is_import:
            idx = self.import_index
            if idx is None or idx >= len(import_map):
                return ResolvedPackageIndex(
                    name=f"<invalid import {idx}>",
                    full_path=f"<invalid import {idx}>",
                    ref_type="import",
                    target_entry=None
                )
            entry = import_map[idx]
            name = entry.object_name
            package = entry.class_package
            full_path = f"{package}.{name}" if package else name
            return ResolvedPackageIndex(
                name=name,
                full_path=full_path,
                ref_type="import",
                target_entry=entry
            )
        else:  # is_export
            idx = self.export_index
            if idx is None or idx >= len(export_map):
                return ResolvedPackageIndex(
                    name=f"<invalid export {idx}>",
                    full_path=f"<invalid export {idx}>",
                    ref_type="export",
                    target_entry=None
                )
            entry = export_map[idx]
            name = entry.object_name
            return ResolvedPackageIndex(
                name=name,
                full_path=name,
                ref_type="export",
                target_entry=entry
            )


@dataclass
class ResolvedPackageIndex:
    """解析后的 PackageIndex 结果"""
    name: str
    full_path: str
    ref_type: str
    target_entry: Any

    def to_dict(self) -> dict:
        """序列化为字典（用于 JSON 输出）"""
        return {
            "type": self.ref_type,
            "name": self.name,
            "full_path": self.full_path,
        }


@dataclass
class ObjectImport:
    """FObjectImport 导入表条目。"""
    class_package: str
    class_name: str
    outer_index: PackageIndex
    object_name: str
    package_name: Optional[str] = None
    b_import_optional: bool = False


@dataclass
class ObjectExport:
    """FObjectExport 导出表条目。"""
    class_index: PackageIndex
    super_index: PackageIndex
    outer_index: PackageIndex
    object_name: str
    object_flags: int
    serial_size: int
    serial_offset: int
    template_index: PackageIndex = field(default_factory=lambda: PackageIndex(0))
    b_forced_export: bool = False
    b_not_for_client: bool = False
    b_not_for_server: bool = False
    b_is_inherited_instance: bool = False
    package_flags: int = 0
    b_not_always_loaded_for_editor_game: bool = False
    b_is_asset: bool = False
    b_generate_public_hash: bool = False
    script_serialization_end_offset: int = 0
    script_serialization_start_offset: int = 0

    @property
    def script_serialization_size(self) -> int:
        """脚本序列化区块大小（end_offset - start_offset）。"""
        return self.script_serialization_end_offset - self.script_serialization_start_offset

    @property
    def has_script_serialization(self) -> bool:
        """是否存在脚本序列化区块。"""
        return self.script_serialization_end_offset > self.script_serialization_start_offset

    # UE5 PreloadDependency 字段 (>= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS)
    first_export_dependency: int = -1
    serialization_before_serialization_dependencies: int = 0
    create_before_serialization_dependencies: int = 0
    serialization_before_create_dependencies: int = 0
    create_before_create_dependencies: int = 0

    properties: List[Any] = field(default_factory=list)
    transforms: Dict[str, Any] = field(default_factory=dict)
    guid: str = ""  # 16 bytes GUID (版本 < 1005 时存在)
