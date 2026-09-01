"""
Object Resources — ObjectImport, ObjectExport, PackageIndex and related read functions.

Extracted from uasset_read.py (core lines 940-3048).
"""

from __future__ import annotations

import logging
import struct
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.link.linker import PackageLinker
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

from uasset_read.archive import FArchive
from uasset_read.serializers.package_summary import PackageFileSummary
from uasset_read.constants import (
    PKG_UnversionedProperties,
    PKG_FilterEditorOnly,
    MAX_IMPORT_COUNT,
    MAX_EXPORT_COUNT,
    UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID,
    UE5_TRACK_OBJECT_EXPORT_IS_INHERITED,
    UE5_OPTIONAL_RESOURCES,
    UE5_SCRIPT_SERIALIZATION_OFFSET,
    UE4_NON_OUTER_PACKAGE_IMPORT,
    UE4_LOAD_FOR_EDITOR_GAME,
    UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT,
    UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS,
    UE4_TemplateIndex_IN_COOKED_EXPORTS,
    UE4_64BIT_EXPORTMAP_SERIALSIZES,
)
from uasset_read.exceptions import ParseError
from uasset_read.models.diagnostics import (
    DIAGNOSTIC_CODE_INVALID_SERIAL_OFFSET,
    DIAGNOSTIC_CODE_INVALID_SERIAL_SIZE,
)


@dataclass
class PackageIndex:
    """FPackageIndex encoding. Index > 0: Export, Index < 0: Import, Index = 0: null"""

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
    """FObjectImport import table entry."""

    class_package: str
    class_name: str
    outer_index: PackageIndex
    object_name: str
    package_name: Optional[str] = None
    b_import_optional: bool = False


@dataclass
class ObjectExport:
    """FObjectExport export table entry."""

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
    # Preload dependency span into summary PreloadDependencyValues
    # (VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS). first=-1 means absent.
    first_export_dependency: int = -1
    serialization_before_serialization_dependencies: int = 0
    create_before_serialization_dependencies: int = 0
    serialization_before_create_dependencies: int = 0
    create_before_create_dependencies: int = 0

    @property
    def script_serialization_size(self) -> int:
        """Script serialization block size (end_offset - start_offset)."""
        return self.script_serialization_end_offset - self.script_serialization_start_offset

    @property
    def has_script_serialization(self) -> bool:
        """Whether script serialization block exists."""
        return self.script_serialization_end_offset > self.script_serialization_start_offset

    properties: List[Any] = field(default_factory=list)
    transforms: Dict[str, Any] = field(default_factory=dict)
    guid: str = ""  # 16 bytes GUID (exists when version < 1005)


def read_import_map(archive: FArchive, summary: PackageFileSummary, name_map: List[str]) -> List[ObjectImport]:
    """Read import table."""
    # CR-05: validate import_count range
    if summary.import_count < 0:
        raise ParseError(f"Negative import count: {summary.import_count}")
    if summary.import_count > MAX_IMPORT_COUNT:
        raise ParseError(f"Import count {summary.import_count} exceeds maximum {MAX_IMPORT_COUNT}")

    archive.seek(summary.import_offset)

    is_filter_editor_only = (summary.package_flags & PKG_FilterEditorOnly) != 0

    # UE4 version used for version gating (high value for UE5 assets)
    file_version = summary.file_version_ue4

    import_map: List[ObjectImport] = []
    for i in range(summary.import_count):
        class_package = archive.read_name(name_map, f"Import[{i}].ClassPackage")
        class_name = archive.read_name(name_map, f"Import[{i}].ClassName")
        outer_index = PackageIndex(archive.read_i32(f"Import[{i}].OuterIndex"))
        object_name = archive.read_name(name_map, f"Import[{i}].ObjectName")

        # PackageName: VER_UE4_NON_OUTER_PACKAGE_IMPORT && !FilterEditorOnly
        # UE5 WITH_EDITORONLY_DATA: only present when file_version >= 519 and not filter-editor-only
        package_name: Optional[str] = None
        if file_version >= UE4_NON_OUTER_PACKAGE_IMPORT and not is_filter_editor_only:
            package_name = archive.read_name(name_map, f"Import[{i}].PackageName")

        # bImportOptional: UE5 >= 1003 (OPTIONAL_RESOURCES)
        b_import_optional = False
        if summary.file_version_ue5 >= UE5_OPTIONAL_RESOURCES:
            b_import_optional = archive.read_bool(f"Import[{i}].bImportOptional")

        import_map.append(
            ObjectImport(
                class_package=class_package,
                class_name=class_name,
                outer_index=outer_index,
                object_name=object_name,
                package_name=package_name,
                b_import_optional=b_import_optional,
            )
        )
    return import_map


def build_imports_list(import_map: List[ObjectImport]) -> List[Dict]:
    """Build imports dependency list (deduplicated, order preserved)."""
    seen = set()
    imports = []
    for imp in import_map:
        key = (imp.class_name, imp.class_package, imp.object_name)
        if key not in seen:
            seen.add(key)
            imports.append({"class": imp.class_name, "package": imp.class_package, "object": imp.object_name})
    return imports


def read_soft_object_paths(archive: FArchive, summary: PackageFileSummary, name_map: List[str]) -> List[Dict]:
    """Read SoftObjectPaths array (UE5.7 specific)."""
    if summary.soft_object_paths_count <= 0 or summary.soft_object_paths_offset <= 0:
        return []

    archive.seek(summary.soft_object_paths_offset)
    soft_refs = []
    for i in range(summary.soft_object_paths_count):
        # UE5 >= 1007 format: double FName
        package_name = archive.read_name(name_map, f"SoftObjectPaths[{i}].PackageName")
        asset_name = archive.read_name(name_map, f"SoftObjectPaths[{i}].AssetName")
        asset_path = f"{package_name}.{asset_name}" if asset_name else package_name
        sub_path = archive.read_fstring(f"SoftObjectPaths[{i}].SubPath")
        soft_refs.append({"asset_path": asset_path, "sub_path": sub_path})
    return soft_refs


def read_export_map(archive: FArchive, summary: PackageFileSummary, name_map: List[str]) -> List[ObjectExport]:
    """Read export table."""
    # CR-05: validate export_count range
    if summary.export_count < 0:
        raise ParseError(f"Negative export count: {summary.export_count}")
    if summary.export_count > MAX_EXPORT_COUNT:
        raise ParseError(f"Export count {summary.export_count} exceeds maximum {MAX_EXPORT_COUNT}")

    archive.seek(summary.export_offset)

    # UE4/UE5 version used for version gating
    file_version = summary.file_version_ue4

    export_map: List[ObjectExport] = []

    for export_idx in range(summary.export_count):
        object_name = ""
        entry_start = archive.tell()
        try:
            class_index = PackageIndex(archive.read_i32(f"Export[{export_idx}].ClassIndex"))
            super_index = PackageIndex(archive.read_i32(f"Export[{export_idx}].SuperIndex"))

            # TemplateIndex: VER_UE4_TemplateIndex_IN_COOKED_EXPORTS (508)
            template_index = PackageIndex(0)
            if file_version >= UE4_TemplateIndex_IN_COOKED_EXPORTS:
                template_index = PackageIndex(archive.read_i32(f"Export[{export_idx}].TemplateIndex"))

            outer_index = PackageIndex(archive.read_i32(f"Export[{export_idx}].OuterIndex"))
            object_name = archive.read_name(name_map, f"Export[{export_idx}].ObjectName")
            object_flags = archive.read_u32(f"Export[{export_idx}].ObjectFlags")

            # SerialSize/Offset: i32 before VER_UE4_64BIT_EXPORTMAP_SERIALSIZES (511), i64 at/after
            if file_version < UE4_64BIT_EXPORTMAP_SERIALSIZES:
                serial_size_offset = archive.tell()
                serial_size = archive.read_i32(f"Export[{export_idx}].SerialSize")
                serial_offset_offset = archive.tell()
                serial_offset = archive.read_i32(f"Export[{export_idx}].SerialOffset")
            else:
                serial_size_offset = archive.tell()
                serial_size = archive.read_i64(f"Export[{export_idx}].SerialSize")
                serial_offset_offset = archive.tell()
                serial_offset = archive.read_i64(f"Export[{export_idx}].SerialOffset")

            # CR-05: validate serial_size/serial_offset non-negative
            # Tolerant: set to 0 and log warning on negative values, subsequent property parsing will be skipped due to size=0
            if serial_size < 0:
                archive._record_structured_diagnostic(
                    code=DIAGNOSTIC_CODE_INVALID_SERIAL_SIZE,
                    stage="read_export_map",
                    offset=serial_size_offset,
                    raw_value=serial_size,
                    fallback="set_to_zero",
                    message=f"Export #{export_idx} serial_size is negative: {serial_size}, set to 0",
                )
                serial_size = 0

            if serial_offset < 0:
                archive._record_structured_diagnostic(
                    code=DIAGNOSTIC_CODE_INVALID_SERIAL_OFFSET,
                    stage="read_export_map",
                    offset=serial_offset_offset,
                    raw_value=serial_offset,
                    fallback="set_to_zero",
                    message=f"Export #{export_idx} serial_offset is negative: {serial_offset}, skipping export",
                )
                serial_offset = 0
                serial_size = 0

            # bool flags (always present)
            b_forced_export = archive.read_bool(f"Export[{export_idx}].bForcedExport")
            b_not_for_client = archive.read_bool(f"Export[{export_idx}].bNotForClient")
            b_not_for_server = archive.read_bool(f"Export[{export_idx}].bNotForServer")

            # PackageGuid: removed in UE5 1005
            package_guid = ""
            if summary.file_version_ue5 < UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID:
                guid_bytes = archive.read(16)
                package_guid = guid_bytes.hex()

            # bIsInheritedInstance: UE5 >= 1006
            b_is_inherited_instance = False
            if summary.file_version_ue5 >= UE5_TRACK_OBJECT_EXPORT_IS_INHERITED:
                b_is_inherited_instance = archive.read_bool(f"Export[{export_idx}].bIsInheritedInstance")

            package_flags = archive.read_u32(f"Export[{export_idx}].PackageFlags")

            # bNotAlwaysLoadedForEditorGame: VER_UE4_LOAD_FOR_EDITOR_GAME (365)
            b_not_always_loaded_for_editor_game = True
            if file_version >= UE4_LOAD_FOR_EDITOR_GAME:
                b_not_always_loaded_for_editor_game = archive.read_bool(
                    f"Export[{export_idx}].bNotAlwaysLoadedForEditorGame"
                )

            # bIsAsset: VER_UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT (485; historical 4.x numbering)
            b_is_asset = False
            if file_version >= UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT:
                b_is_asset = archive.read_bool(f"Export[{export_idx}].bIsAsset")

            # bGeneratePublicHash: UE5 >= 1003 (OPTIONAL_RESOURCES)
            b_generate_public_hash = False
            if summary.file_version_ue5 >= UE5_OPTIONAL_RESOURCES:
                b_generate_public_hash = archive.read_bool(f"Export[{export_idx}].bGeneratePublicHash")

            # Dependency arrays: VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS (507)
            # Span into summary PreloadDependencyValues:
            # [FirstExportDependency, FirstExportDependency + sum of the 4 counts)
            first_export_dependency = -1
            ser_before_ser_deps = 0
            create_before_ser_deps = 0
            ser_before_create_deps = 0
            create_before_create_deps = 0
            if file_version >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:
                first_export_dependency = archive.read_i32(f"Export[{export_idx}].FirstExportDependency")
                ser_before_ser_deps = archive.read_i32(
                    f"Export[{export_idx}].SerializationBeforeSerializationDeps"
                )
                create_before_ser_deps = archive.read_i32(
                    f"Export[{export_idx}].CreateBeforeSerializationDeps"
                )
                ser_before_create_deps = archive.read_i32(
                    f"Export[{export_idx}].SerializationBeforeCreateDeps"
                )
                create_before_create_deps = archive.read_i32(f"Export[{export_idx}].CreateBeforeCreateDeps")

            # ScriptSerialization offsets (UE5 >= 1010, only for versioned properties)
            script_serialization_start_offset = 0
            script_serialization_end_offset = 0
            uses_unversioned = (summary.package_flags & PKG_UnversionedProperties) != 0
            if not uses_unversioned and summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
                script_serialization_start_offset = archive.read_i64(
                    f"Export[{export_idx}].ScriptSerializationStartOffset"
                )
                script_serialization_end_offset = archive.read_i64(f"Export[{export_idx}].ScriptSerializationEndOffset")
                # CR-05: validate non-negative (Tolerant: set to 0 and log warning on negative values)
                if script_serialization_start_offset < 0:
                    logger.debug(
                        "Export #%d ScriptSerializationStartOffset is negative: %d, set to 0",
                        export_idx,
                        script_serialization_start_offset,
                    )
                    script_serialization_start_offset = 0
                if script_serialization_end_offset < 0:
                    logger.debug(
                        "Export #%d ScriptSerializationEndOffset is negative: %d, set to 0",
                        export_idx,
                        script_serialization_end_offset,
                    )
                    script_serialization_end_offset = 0

            export_map.append(
                ObjectExport(
                    class_index=class_index,
                    super_index=super_index,
                    template_index=template_index,
                    outer_index=outer_index,
                    object_name=object_name,
                    object_flags=object_flags,
                    serial_size=serial_size,
                    serial_offset=serial_offset,
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
                    first_export_dependency=first_export_dependency,
                    serialization_before_serialization_dependencies=ser_before_ser_deps,
                    create_before_serialization_dependencies=create_before_ser_deps,
                    serialization_before_create_dependencies=ser_before_create_deps,
                    create_before_create_dependencies=create_before_create_deps,
                )
            )
        except (struct.error, OSError, ValueError, AttributeError) as e:
            # A failed entry leaves the stream position unknown; continuing
            # would silently renumber later exports. Stop the table instead.
            archive._record_structured_diagnostic(
                code="EXPORT_TABLE_TRUNCATED",
                stage="read_export_map",
                offset=entry_start,
                fallback="stop_table",
                message=(
                    f"Export #{export_idx} parse failed ({type(e).__name__}: {e}); "
                    f"stopped export table read with {len(export_map)}/{summary.export_count} entries"
                ),
            )
            logger.warning("Export #%d parse failed (%s); stopping export table read", export_idx, e)
            break
    return export_map


def get_asset_class(
    export: ObjectExport, import_map: List[ObjectImport], export_map: List[ObjectExport]
) -> Optional[str]:
    """Identify asset type from export entry."""
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
    class_index: PackageIndex, import_map: List[ObjectImport], export_map: List[ObjectExport]
) -> Optional[str]:
    """Resolve class name from PackageIndex."""
    if class_index.is_import:
        import_idx = class_index.to_import_index()
        if 0 <= import_idx < len(import_map):
            return import_map[import_idx].object_name
    elif class_index.is_export:
        export_idx = class_index.to_export_index()
        if 0 <= export_idx < len(export_map):
            return export_map[export_idx].object_name
    return None


def detect_blueprint(export: ObjectExport, import_map: List[ObjectImport], export_map: List[ObjectExport]) -> bool:
    """Detect whether export is a Blueprint asset."""
    class_name = get_asset_class(export, import_map, export_map)
    return class_name is not None and "Blueprint" in class_name


def detect_blueprint_generated_class(
    export: ObjectExport, import_map: List[ObjectImport], export_map: List[ObjectExport]
) -> bool:
    """Detect whether export is a BlueprintGeneratedClass.

    Checks import.object_name rather than class_name,
    because BPGC's import.class_name is "Class" and object_name is "BlueprintGeneratedClass".
    """
    if export.class_index.is_import:
        idx = export.class_index.to_import_index()
        if 0 <= idx < len(import_map):
            return "BlueprintGeneratedClass" in import_map[idx].object_name
    return False


def resolve_class_name_with_linker(
    class_index: PackageIndex,
    linker: "PackageLinker",
) -> Optional[str]:
    """Resolve class name from PackageIndex (via linker)."""
    if class_index.is_null:
        return None
    inst = linker.resolve_package_index(class_index)
    return inst.object_name if inst else None


def get_asset_class_with_linker(
    export: ObjectExport,
    linker: "PackageLinker",
) -> Optional[str]:
    """Identify asset type from export entry (via linker)."""
    inst = linker.resolve_package_index(export.class_index)
    return inst.object_name if inst else None


def detect_blueprint_with_linker(
    export: ObjectExport,
    linker: "PackageLinker",
) -> bool:
    """Detect whether export is a Blueprint asset (via linker)."""
    cls = get_asset_class_with_linker(export, linker)
    return cls is not None and "Blueprint" in cls


def resolve_parent_class_with_linker(
    super_index: PackageIndex,
    linker: "PackageLinker",
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve ParentClass FPackageIndex to object name (via linker).

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
    Find the main BlueprintGeneratedClass export (equivalent migration from uasset_read.py section 3063-3092).

    Uses object_name matching + serial_size maximum principle.
    The main BPGC's object_name is typically asset_name + "_C".
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
    super_index: PackageIndex, import_map: List[ObjectImport], export_map: List[ObjectExport]
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
    pkg_idx: PackageIndex, import_map: List[ObjectImport], export_map: List[ObjectExport], name_map: List[str]
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
