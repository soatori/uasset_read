"""Object Resources 解析函数 — resolve_class_name, detect_blueprint 等工具函数。"""
from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.link.linker import PackageLinker

from .models import PackageIndex, ObjectImport, ObjectExport


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
    package_refs: Dict[str, set] = {}
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
    Resolve ParentClass FPackageIndex to full UE path (通过 linker)。

    Returns:
        Tuple of (resolved_path, warning_if_any)
        - (full_path, None) on success, e.g. "/Script/Engine.Character"
        - (None, warning_string) on failure
    """
    if super_index.is_null:
        return None, None
    inst = linker.resolve_package_index(super_index)
    if inst is not None:
        # 构建完整 UE 路径：class_package.object_name
        # 例如 /Script/Engine.Character
        if inst.class_package:
            return f"{inst.class_package}.{inst.object_name}", None
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

    # Fallback: try matching by simple name (strip path prefix from asset_name)
    if not candidates:
        simple_asset_name = asset_name.split("/")[-1] if "/" in asset_name else asset_name
        for export in export_map:
            if detect_blueprint_generated_class(export, import_map, export_map):
                if export.object_name and (export.object_name == simple_asset_name or export.object_name == simple_asset_name + "_C"):
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
    Resolve ParentClass FPackageIndex to full UE path (BLUE-02).

    Per D-09: only direct parent (no inheritance chain).
    Per D-10: resolve to ImportMap/ExportMap object name.
    Per D-11: return raw index + warning on resolution failure.

    Returns:
        Tuple of (resolved_path, warning_if_any)
        - (full_path, None) on success, e.g. "/Script/Engine.Character"
        - (None, warning_string) on failure
    """
    if super_index.is_null:
        return None, None

    if super_index.is_import:
        import_idx = super_index.to_import_index()
        if 0 <= import_idx < len(import_map):
            imp = import_map[import_idx]
            # 构建完整 UE 路径：class_package.object_name
            if imp.class_package:
                return f"{imp.class_package}.{imp.object_name}", None
            return imp.object_name, None
        else:
            return None, f"Parent import index out of range: {super_index.index}"

    elif super_index.is_export:
        export_idx = super_index.to_export_index()
        if 0 <= export_idx < len(export_map):
            # 对于 export，返回 object_name
            # export 的 class 信息在 class_index 中，需要额外解析
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
