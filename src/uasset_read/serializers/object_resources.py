"""
Object Resources — ObjectImport, ObjectExport, PackageIndex 及相关读取函数。

从 uasset_read.py 提取（第 940-3048 行核心部分）。
"""

from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

from uasset_read.archive import FArchive
from uasset_read.serializers.package_summary import PackageFileSummary
from uasset_read.constants import (
    PKG_Cooked, PKG_UnversionedProperties,
    MAX_IMPORT_COUNT, MAX_EXPORT_COUNT,
    UE4_NON_OUTER_PACKAGE_IMPORT, UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS,
    UE4_LOAD_FOR_EDITOR_GAME, UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT,
    VER_UE4_64BIT_EXPORTOFFSETS, VER_UE4_TemplateIndex_IN_COOKED_EXPORTS,
    UE4_ADDED_SEARCHABLE_NAMES, UE4_ADD_STRING_ASSET_REFERENCES_MAP,
    UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID, UE5_TRACK_OBJECT_EXPORT_IS_INHERITED,
    UE5_OPTIONAL_RESOURCES, UE5_SCRIPT_SERIALIZATION_OFFSET,
    UE5_ADD_SOFTOBJECTPATH_LIST, UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES,
)
from uasset_read.exceptions import ParseError, ErrorContext


@dataclass
class PackageIndex:
    """FPackageIndex 编码。Index > 0: Export, Index < 0: Import, Index = 0: null"""
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

    def to_import_index(self) -> int:
        return -self.index - 1

    def to_export_index(self) -> int:
        return self.index - 1


@dataclass
class ObjectImport:
    """FObjectImport 导入表条目。"""
    class_package: str
    class_name: str
    outer_index: PackageIndex
    object_name: str
    package_name: Optional[str] = None
    b_import_optional: Optional[bool] = None


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
    b_is_inherited_instance: Optional[bool] = None
    package_flags: int = 0
    b_not_always_loaded_for_editor_game: Optional[bool] = None
    b_is_asset: Optional[bool] = None
    b_generate_public_hash: Optional[bool] = None
    script_serial_size: int = 0
    script_serial_offset: int = 0
    properties: List[Any] = field(default_factory=list)
    transforms: Dict[str, Any] = field(default_factory=dict)


def read_import_map(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[ObjectImport]:
    """读取导入表。"""
    archive.seek(summary.import_offset)

    is_ue4_file = summary.legacy_file_version > -8
    is_filter_editor_only = False

    import_map: List[ObjectImport] = []
    for _ in range(summary.import_count):
        class_package = archive.read_name(name_map)
        class_name = archive.read_name(name_map)
        outer_index = PackageIndex(archive.read_i32())
        object_name = archive.read_name(name_map)

        # PackageName: UEVer >= 518 && !IsFilterEditorOnly
        has_package_name = False
        if not is_filter_editor_only:
            if is_ue4_file and summary.file_version_ue4 >= UE4_NON_OUTER_PACKAGE_IMPORT:
                has_package_name = True
            elif not is_ue4_file:
                has_package_name = True

        package_name: Optional[str] = None
        if has_package_name:
            package_name = archive.read_name(name_map)

        # bImportOptional: UEVer >= OPTIONAL_RESOURCES (1003)
        b_import_optional: Optional[bool] = None
        if is_ue4_file and summary.file_version_ue4 >= UE5_OPTIONAL_RESOURCES:
            b_import_optional = archive.read_bool()
        elif not is_ue4_file and summary.file_version_ue5 >= UE5_OPTIONAL_RESOURCES:
            b_import_optional = archive.read_bool()

        import_map.append(ObjectImport(
            class_package=class_package, class_name=class_name,
            outer_index=outer_index, object_name=object_name,
            package_name=package_name, b_import_optional=b_import_optional
        ))
    return import_map


def build_imports_list(import_map: List[ObjectImport]) -> List[Dict]:
    """构建 imports 依赖列表（去重，保持顺序）。"""
    seen = set()
    imports = []
    for imp in import_map:
        key = (imp.class_name, imp.class_package, imp.object_name)
        if key not in seen:
            seen.add(key)
            imports.append({
                "class": imp.class_name,
                "package": imp.class_package,
                "object": imp.object_name
            })
    return imports


def read_soft_object_paths(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[Dict]:
    """读取 SoftObjectPaths 数组。"""
    is_ue5_file = summary.legacy_file_version <= -8
    if not is_ue5_file or summary.file_version_ue5 < UE5_ADD_SOFTOBJECTPATH_LIST:
        return []
    if summary.soft_object_paths_count <= 0 or summary.soft_object_paths_offset <= 0:
        return []

    archive.seek(summary.soft_object_paths_offset)
    soft_refs = []
    for _ in range(summary.soft_object_paths_count):
        if summary.file_version_ue5 >= UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES:
            package_name = archive.read_name(name_map)
            asset_name = archive.read_name(name_map)
            asset_path = f"{package_name}.{asset_name}" if asset_name else package_name
            sub_path = archive.read_fstring()
        else:
            asset_path = archive.read_name(name_map)
            sub_path = archive.read_fstring()
        soft_refs.append({"asset_path": asset_path, "sub_path": sub_path})
    return soft_refs


def detect_circular_deps(import_map: List[ObjectImport]) -> List[List[str]]:
    """检测 ImportMap 中的高密度依赖作为潜在循环警告。"""
    if not import_map:
        return []
    package_refs: Dict[str, int] = {}
    for imp in import_map:
        pkg = imp.class_package
        package_refs[pkg] = package_refs.get(pkg, 0) + 1
    return [[pkg, pkg] for pkg, count in package_refs.items() if count > 1]


def read_export_map(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[ObjectExport]:
    """读取导出表。"""
    archive.seek(summary.export_offset)

    export_map: List[ObjectExport] = []
    is_ue5_file = summary.legacy_file_version <= -8
    effective_ue4_version = summary.file_version_ue4 if not is_ue5_file else 1000

    for export_idx in range(summary.export_count):
        object_name = ""
        try:
            class_index = PackageIndex(archive.read_i32())
            super_index = PackageIndex(archive.read_i32())

            # TemplateIndex (UE4 >= 508)
            template_index = PackageIndex(0)
            if effective_ue4_version >= VER_UE4_TemplateIndex_IN_COOKED_EXPORTS:
                template_index = PackageIndex(archive.read_i32())

            outer_index = PackageIndex(archive.read_i32())
            object_name = archive.read_name(name_map)
            object_flags = archive.read_u32()

            # SerialSize/Offset
            if effective_ue4_version >= VER_UE4_64BIT_EXPORTOFFSETS:
                serial_size = archive.read_i64()
                serial_offset = archive.read_i64()
            else:
                serial_size = archive.read_i32()
                serial_offset = archive.read_i32()

            # bool flags
            b_forced_export = archive.read_bool()
            b_not_for_client = archive.read_bool()
            b_not_for_server = archive.read_bool()

            # PackageGuid (UE5 < 1005)
            if is_ue5_file and summary.file_version_ue5 < UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID:
                archive.read_bytes(16)

            # bIsInheritedInstance (UE5 >= 1006)
            b_is_inherited_instance = None
            if is_ue5_file and summary.file_version_ue5 >= UE5_TRACK_OBJECT_EXPORT_IS_INHERITED:
                b_is_inherited_instance = archive.read_bool()

            package_flags = archive.read_u32()

            # Other bool flags
            b_not_always_loaded_for_editor_game = None
            b_is_asset = None
            b_generate_public_hash = None

            if effective_ue4_version >= UE4_LOAD_FOR_EDITOR_GAME:
                b_not_always_loaded_for_editor_game = archive.read_bool()
            if effective_ue4_version >= UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT:
                b_is_asset = archive.read_bool()
            if is_ue5_file and summary.file_version_ue5 >= UE5_OPTIONAL_RESOURCES:
                b_generate_public_hash = archive.read_bool()

            # Dependency arrays (UE4 >= 507)
            if effective_ue4_version >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:
                archive.read_i32()  # first_export_dependency
                archive.read_i32()  # serialization_before_serialization_deps
                archive.read_i32()  # create_before_serialization_deps
                archive.read_i32()  # serialization_before_create_deps
                archive.read_i32()  # create_before_create_deps

            # ScriptSerialization offsets
            script_serial_offset = 0
            script_serial_size = 0
            uses_unversioned = (summary.package_flags & PKG_UnversionedProperties) != 0
            if is_ue5_file and not uses_unversioned and summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
                script_serial_offset = archive.read_i64()
                script_serial_size = archive.read_i64()

            export_map.append(ObjectExport(
                class_index=class_index, super_index=super_index,
                template_index=template_index, outer_index=outer_index,
                object_name=object_name, object_flags=object_flags,
                serial_size=serial_size, serial_offset=serial_offset,
                b_forced_export=b_forced_export,
                b_not_for_client=b_not_for_client,
                b_not_for_server=b_not_for_server,
                b_is_inherited_instance=b_is_inherited_instance,
                package_flags=package_flags,
                b_not_always_loaded_for_editor_game=b_not_always_loaded_for_editor_game,
                b_is_asset=b_is_asset,
                b_generate_public_hash=b_generate_public_hash,
                script_serial_size=script_serial_size,
                script_serial_offset=script_serial_offset
            ))
        except Exception as e:
            context = ErrorContext(
                offset=archive.tell(), phase="export_map", operation="read_export",
                context_name=object_name, export_index=export_idx
            )
            raise ParseError(
                f"导出表解析失败（导出 #{export_idx}）：{str(e)}",
                partial_result={"export_map": export_map},
                context=context
            )
    return export_map


def get_asset_class(
    export: ObjectExport,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> Optional[str]:
    """从导出条目识别资产类型。"""
    if export.class_index.is_import:
        import_idx = export.class_index.to_import_index()
        if 0 <= import_idx < len(import_map):
            return import_map[import_idx].object_name
    elif export.class_index.is_export:
        export_idx = export.class_index.to_export_index()
        if 0 <= export_idx < len(export_map):
            return export_map[export_idx].object_name
    return None


def resolve_class_name(
    class_index: PackageIndex,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> Optional[str]:
    """从 PackageIndex 解析类名。"""
    if class_index.is_import:
        import_idx = class_index.to_import_index()
        if 0 <= import_idx < len(import_map):
            return import_map[import_idx].object_name
    elif class_index.is_export:
        export_idx = class_index.to_export_index()
        if 0 <= export_idx < len(export_map):
            return export_map[export_idx].object_name
    return None


def detect_blueprint(
    export: ObjectExport,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> bool:
    """检测导出是否为蓝图资产。"""
    class_name = get_asset_class(export, import_map, export_map)
    return class_name is not None and "Blueprint" in class_name


def detect_blueprint_generated_class(
    export: ObjectExport,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> bool:
    """检测导出是否为 BlueprintGeneratedClass。"""
    if export.class_index.is_import:
        idx = export.class_index.to_import_index()
        if 0 <= idx < len(import_map):
            return "BlueprintGeneratedClass" in import_map[idx].class_name
    return False


def validate_package_index(
    index: PackageIndex,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    context: str = ""
) -> Optional[str]:
    """PackageIndex 完整验证。"""
    if index.is_null:
        return None
    if index.is_import:
        import_idx = index.to_import_index()
        if not (0 <= import_idx < len(import_map)):
            return f"PackageIndex {index.index} import out of range at {context}"
        return None
    elif index.is_export:
        export_idx = index.to_export_index()
        if not (0 <= export_idx < len(export_map)):
            return f"PackageIndex {index.index} export out of range at {context}"
        return None
def resolve_package_index_to_reference(
    pkg_idx: PackageIndex,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    name_map: List[str]
) -> Optional[Dict[str, Any]]:
    """解析 FPackageIndex 为可读对象引用信息。

    Phase 11-02: 增强 ObjectProperty 解析返回可读对象引用。

    Args:
        pkg_idx: PackageIndex 对象
        import_map: ImportMap 列表
        export_map: ExportMap 列表
        name_map: NameMap 列表

    Returns:
        None if pkg_idx.is_null
        {"type": "import", "class_name": str, "object_name": str, "package": str} if import
        {"type": "export", "class_name": str, "object_name": str} if export
    """
    if pkg_idx.is_null:
        return None

    if pkg_idx.is_import:
        imp_idx = pkg_idx.to_import_index()
        if 0 <= imp_idx < len(import_map):
            imp = import_map[imp_idx]
            class_name = name_map[imp.class_name] if isinstance(imp.class_name, int) else imp.class_name
            object_name = name_map[imp.object_name] if isinstance(imp.object_name, int) else imp.object_name
            package = name_map[imp.class_package] if isinstance(imp.class_package, int) else imp.class_package
            return {
                "type": "import",
                "source": "import_map",
                "class_name": class_name,
                "object_name": object_name,
                "package": package
            }

    elif pkg_idx.is_export:
        exp_idx = pkg_idx.to_export_index()
        if 0 <= exp_idx < len(export_map):
            exp = export_map[exp_idx]
            class_name = _resolve_class_name(exp.class_index, import_map, export_map, name_map)
            object_name = name_map[exp.object_name] if isinstance(exp.object_name, int) else exp.object_name
            return {
                "type": "export",
                "class_name": class_name,
                "object_name": object_name
            }

    return None


def _resolve_class_name(
    class_index: PackageIndex,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    name_map: List[str]
) -> str:
    """递归解析 class_index 获取类名。"""
    if class_index.is_null or class_index.index == 0:
        return "None"

    resolved = resolve_package_index_to_reference(class_index, import_map, export_map, name_map)
    if resolved:
        return resolved.get("class_name", "Unknown")
    return "Unknown"


def find_main_blueprint_generated_class(
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    asset_name: str,
) -> Optional[ObjectExport]:
    """
    查找主 BlueprintGeneratedClass 导出（等价迁移 uasset_read.py §3063-3092）。

    使用 object_name 匹配 + serial_size 最大原则。
    主 BPGC 的 object_name 通常为 asset_name + "_C"。
    """
    candidates = []
    for export in export_map:
        if detect_blueprint_generated_class(export, import_map, export_map):
            if export.object_name and export.object_name.startswith(asset_name):
                candidates.append(export)
    if candidates:
        return max(candidates, key=lambda e: e.serial_size)
    return None


def resolve_parent_class(
    super_index: PackageIndex,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve ParentClass FPackageIndex to object name (BLUE-02).

    Per D-09: only direct parent (no inheritance chain).
    Per D-10: resolve to ImportMap/ExportMap object name.
    Per D-11: return raw index + warning on resolution failure.

    Returns:
        Tuple of (resolved_name, warning_if_any)
        - (class_name, None) on success
        - (None, warning_string) on failure
    """
    if super_index.is_null:
        return None, None

    if super_index.is_import:
        import_idx = super_index.to_import_index()
        if 0 <= import_idx < len(import_map):
            return import_map[import_idx].object_name, None
        else:
            return None, f"Parent import index out of range: {super_index.index}"

    elif super_index.is_export:
        export_idx = super_index.to_export_index()
        if 0 <= export_idx < len(export_map):
            return export_map[export_idx].object_name, None
        else:
            return None, f"Parent export index out of range: {super_index.index}"

    return None, f"Unknown parent index type: {super_index.index}"
