"""
Object Resources — ObjectImport, ObjectExport, PackageIndex 及相关读取函数。

从 uasset_read.py 提取（第 940-3048 行核心部分）。
"""

import logging
from typing import Optional, List, Dict, Any, Tuple, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.link.linker import PackageLinker
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

from uasset_read.archive import FArchive
from uasset_read.serializers.package_summary import PackageFileSummary
from uasset_read.constants import (
    PKG_Cooked, PKG_UnversionedProperties, PKG_FilterEditorOnly,
    MAX_IMPORT_COUNT, MAX_EXPORT_COUNT,
    UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID, UE5_TRACK_OBJECT_EXPORT_IS_INHERITED,
    UE5_OPTIONAL_RESOURCES, UE5_SCRIPT_SERIALIZATION_OFFSET,
    UE5_ADD_SOFTOBJECTPATH_LIST, UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES,
    UE4_NON_OUTER_PACKAGE_IMPORT, UE4_LOAD_FOR_EDITOR_GAME,
    UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT, UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS,
    UE4_TemplateIndex_IN_COOKED_EXPORTS, UE4_64BIT_EXPORTMAP_SERIALSIZES,
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
    properties: List[Any] = field(default_factory=list)
    transforms: Dict[str, Any] = field(default_factory=dict)
    guid: str = ""  # 16 bytes GUID (版本 < 1005 时存在)


def read_import_map(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[ObjectImport]:
    """读取导入表。"""
    # CR-05: 验证 import_count 范围
    if summary.import_count < 0:
        raise ParseError(f"负数导入计数: {summary.import_count}")
    if summary.import_count > MAX_IMPORT_COUNT:
        raise ParseError(f"导入计数 {summary.import_count} 超过最大值 {MAX_IMPORT_COUNT}")

    archive.seek(summary.import_offset)

    is_filter_editor_only = (summary.package_flags & PKG_FilterEditorOnly) != 0

    # UE4 version used for version gating (high value for UE5 assets)
    file_version = summary.file_version_ue4

    import_map: List[ObjectImport] = []
    for _ in range(summary.import_count):
        class_package = archive.read_name(name_map)
        class_name = archive.read_name(name_map)
        outer_index = PackageIndex(archive.read_i32())
        object_name = archive.read_name(name_map)

        # PackageName: VER_UE4_NON_OUTER_PACKAGE_IMPORT && !FilterEditorOnly
        # UE5 WITH_EDITORONLY_DATA: only present when file_version >= 519 and not filter-editor-only
        package_name: Optional[str] = None
        if file_version >= UE4_NON_OUTER_PACKAGE_IMPORT and not is_filter_editor_only:
            package_name = archive.read_name(name_map)

        # bImportOptional: UE5 >= 1003 (OPTIONAL_RESOURCES)
        b_import_optional = False
        if summary.file_version_ue5 >= UE5_OPTIONAL_RESOURCES:
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
    """读取 SoftObjectPaths 数组（UE5.7 专用）。"""
    if summary.soft_object_paths_count <= 0 or summary.soft_object_paths_offset <= 0:
        return []

    archive.seek(summary.soft_object_paths_offset)
    soft_refs = []
    for _ in range(summary.soft_object_paths_count):
        # UE5 >= 1007 format: double FName
        package_name = archive.read_name(name_map)
        asset_name = archive.read_name(name_map)
        asset_path = f"{package_name}.{asset_name}" if asset_name else package_name
        sub_path = archive.read_fstring()
        soft_refs.append({"asset_path": asset_path, "sub_path": sub_path})
    return soft_refs


def detect_circular_deps(import_map: List[ObjectImport]) -> List[List[str]]:
    """检测 ImportMap 中的包依赖循环。

    通过分析 ImportMap 中的包引用，检测潜在的循环依赖。
    跳过 /Script/ 开头的引擎包（出现多次是正常的）。

    Returns:
        循环依赖链列表，每个链是一组相互引用的包名
    """
    if not import_map:
        return []

    # 收集包引用关系
    package_refs: Dict[str, Set[str]] = {}
    for imp in import_map:
        # 获取源包名（从 class_package 或 object_name）
        source_pkg = ""
        if imp.class_package:
            if isinstance(imp.class_package, int):
                # 需要 name_map，但当前上下文没有
                continue
            source_pkg = imp.class_package
        elif imp.package_name:
            source_pkg = imp.package_name if isinstance(imp.package_name, str) else ""

        # 跳过引擎包
        if source_pkg.startswith("/Script/"):
            continue

        # 记录引用关系
        if source_pkg not in package_refs:
            package_refs[source_pkg] = set()

    # 当前实现：返回空列表
    # 真正的循环依赖检测需要跨包解析和完整的依赖图分析
    # 这需要在链接器层面实现，而不是在 ImportMap 解析阶段
    return []


def read_export_map(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[ObjectExport]:
    """读取导出表。"""
    # CR-05: 验证 export_count 范围
    if summary.export_count < 0:
        raise ParseError(f"负数导出计数: {summary.export_count}")
    if summary.export_count > MAX_EXPORT_COUNT:
        raise ParseError(f"导出计数 {summary.export_count} 超过最大值 {MAX_EXPORT_COUNT}")

    archive.seek(summary.export_offset)

    # UE4/UE5 version used for version gating
    file_version = summary.file_version_ue4

    export_map: List[ObjectExport] = []

    for export_idx in range(summary.export_count):
        object_name = ""
        try:
            class_index = PackageIndex(archive.read_i32())
            super_index = PackageIndex(archive.read_i32())

            # TemplateIndex: VER_UE4_TemplateIndex_IN_COOKED_EXPORTS (507)
            template_index = PackageIndex(0)
            if file_version >= UE4_TemplateIndex_IN_COOKED_EXPORTS:
                template_index = PackageIndex(archive.read_i32())

            outer_index = PackageIndex(archive.read_i32())
            object_name = archive.read_name(name_map)
            object_flags = archive.read_u32()

            # SerialSize/Offset: i32 before VER_UE4_64BIT_EXPORTMAP_SERIALSIZES (510), i64 after
            if file_version < UE4_64BIT_EXPORTMAP_SERIALSIZES:
                serial_size = archive.read_i32()
                serial_offset = archive.read_i32()
            else:
                serial_size = archive.read_i64()
                serial_offset = archive.read_i64()

            # CR-05: 验证 serial_size/serial_offset 非负
            # Tolerant: 负数时设为 0 并记录 warning，后续属性解析会因 size=0 被跳过
            if serial_size < 0:
                logger.warning(
                    "Export #%d serial_size 为负数: %d, 设为 0",
                    export_idx, serial_size,
                )
                serial_size = 0

            if serial_offset < 0:
                logger.warning(
                    "Export #%d serial_offset 为负数: %d, 跳过该 export",
                    export_idx, serial_offset,
                )
                serial_offset = 0
                serial_size = 0

            # bool flags (always present)
            b_forced_export = archive.read_bool()
            b_not_for_client = archive.read_bool()
            b_not_for_server = archive.read_bool()

            # PackageGuid: removed in UE5 1005
            package_guid = ""
            if summary.file_version_ue5 < UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID:
                guid_bytes = archive.read(16)
                package_guid = guid_bytes.hex()

            # bIsInheritedInstance: UE5 >= 1006
            b_is_inherited_instance = False
            if summary.file_version_ue5 >= UE5_TRACK_OBJECT_EXPORT_IS_INHERITED:
                b_is_inherited_instance = archive.read_bool()

            package_flags = archive.read_u32()

            # bNotAlwaysLoadedForEditorGame: VER_UE4_LOAD_FOR_EDITOR_GAME (364)
            b_not_always_loaded_for_editor_game = True
            if file_version >= UE4_LOAD_FOR_EDITOR_GAME:
                b_not_always_loaded_for_editor_game = archive.read_bool()

            # bIsAsset: VER_UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT (484)
            b_is_asset = False
            if file_version >= UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT:
                b_is_asset = archive.read_bool()

            # bGeneratePublicHash: UE5 >= 1003 (OPTIONAL_RESOURCES)
            b_generate_public_hash = False
            if summary.file_version_ue5 >= UE5_OPTIONAL_RESOURCES:
                b_generate_public_hash = archive.read_bool()

            # Dependency arrays: VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS (506)
            if file_version >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:
                archive.read_i32()  # first_export_dependency
                archive.read_i32()  # serialization_before_serialization_deps
                archive.read_i32()  # create_before_serialization_deps
                archive.read_i32()  # serialization_before_create_deps
                archive.read_i32()  # create_before_create_deps

            # ScriptSerialization offsets (UE5 >= 1010, only for versioned properties)
            script_serialization_start_offset = 0
            script_serialization_end_offset = 0
            uses_unversioned = (summary.package_flags & PKG_UnversionedProperties) != 0
            if (
                not uses_unversioned
                and summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET
            ):
                script_serialization_start_offset = archive.read_i64()
                script_serialization_end_offset = archive.read_i64()
                # CR-05: 验证非负（Tolerant: 负数时设为 0 并记录 warning）
                if script_serialization_start_offset < 0:
                    logger.warning(
                        "Export #%d ScriptSerializationStartOffset 为负数: %d, 设为 0",
                        export_idx, script_serialization_start_offset,
                    )
                    script_serialization_start_offset = 0
                if script_serialization_end_offset < 0:
                    logger.warning(
                        "Export #%d ScriptSerializationEndOffset 为负数: %d, 设为 0",
                        export_idx, script_serialization_end_offset,
                    )
                    script_serialization_end_offset = 0

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
                script_serialization_end_offset=script_serialization_end_offset,
                script_serialization_start_offset=script_serialization_start_offset,
                guid=package_guid,
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
    """检测导出是否为 BlueprintGeneratedClass。

    检查 import.object_name 而非 class_name，
    因为 BPGC 的 import.class_name 为 "Class"，object_name 为 "BlueprintGeneratedClass"。
    """
    if export.class_index.is_import:
        idx = export.class_index.to_import_index()
        if 0 <= idx < len(import_map):
            return "BlueprintGeneratedClass" in import_map[idx].object_name
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


def resolve_class_name_with_linker(
    class_index: PackageIndex,
    linker: "PackageLinker",
) -> Optional[str]:
    """从 PackageIndex 解析类名（通过 linker）。"""
    if class_index.is_null:
        return None
    inst = linker.resolve_package_index(class_index)
    return inst.object_name if inst else None


def get_asset_class_with_linker(
    export: ObjectExport,
    linker: "PackageLinker",
) -> Optional[str]:
    """从导出条目识别资产类型（通过 linker）。"""
    inst = linker.resolve_package_index(export.class_index)
    return inst.object_name if inst else None


def detect_blueprint_with_linker(
    export: ObjectExport,
    linker: "PackageLinker",
) -> bool:
    """检测导出是否为蓝图资产（通过 linker）。"""
    cls = get_asset_class_with_linker(export, linker)
    return cls is not None and "Blueprint" in cls


def resolve_parent_class_with_linker(
    super_index: PackageIndex,
    linker: "PackageLinker",
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve ParentClass FPackageIndex to object name (通过 linker)。

    Returns:
        Tuple of (resolved_name, warning_if_any)
        - (class_name, None) on success
        - (None, warning_string) on failure
    """
    if super_index.is_null:
        return None, None
    inst = linker.resolve_package_index(super_index)
    if inst is not None:
        return inst.object_name, None
    return None, f"Parent resolution failed for index {super_index.index}"


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


def resolve_package_index_to_reference(
    pkg_idx: PackageIndex,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    name_map: List[str]
) -> Optional[Dict[str, Any]]:
    """Resolve PackageIndex to reference dict using raw maps (no linker).

    This function provides a fallback when linker is not available.
    It resolves PackageIndex to a reference dict with object metadata.

    Args:
        pkg_idx: PackageIndex to resolve
        import_map: List of ObjectImport entries
        export_map: List of ObjectExport entries
        name_map: Name map for class name resolution

    Returns:
        Dict with keys: source, (import_index or export_index), object_name, class_name, outer_name
        or None if index is null or out of bounds
    """
    if pkg_idx.is_null:
        return None

    if pkg_idx.is_import:
        idx = pkg_idx.to_import_index()
        if 0 <= idx < len(import_map):
            imp = import_map[idx]
            return {
                "source": "import_map",
                "import_index": idx,
                "object_name": imp.object_name,
                "class_name": imp.class_name,
                "outer_name": imp.package_name or imp.class_package,
            }
        else:
            return None

    if pkg_idx.is_export:
        idx = pkg_idx.to_export_index()
        if 0 <= idx < len(export_map):
            exp = export_map[idx]
            # Resolve class_name using get_asset_class (no linker available)
            class_name = get_asset_class(exp, import_map, export_map)
            # Resolve outer_name from export_map (no linker available)
            outer_name = None
            if exp.outer_index.is_export and exp.outer_index.to_export_index() < len(export_map):
                outer_exp = export_map[exp.outer_index.to_export_index()]
                outer_name = outer_exp.object_name
            return {
                "source": "export_map",
                "export_index": idx,
                "object_name": exp.object_name,
                "class_name": class_name,
                "outer_name": outer_name,
            }
        else:
            return None

    return None
