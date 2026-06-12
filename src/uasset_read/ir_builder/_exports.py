"""IR 构建层 — Export 相关函数。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.ir_builder._utils import _safe_str, _safe_int, _normalize_guid
from uasset_read.models.ir import (
    ExportIR,
    ExportRawIR,
    PropertyIR,
)
from uasset_read.serializers.object_resources import PackageIndex

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult


def _build_exports(result: "ParseResult") -> list[ExportIR]:
    exports = []
    for idx, export in enumerate(result.export_map or []):
        try:
            export_ir = _build_export_ir(idx, export, result)
            exports.append(export_ir)
        except Exception:
            # tolerant 模式：跳过失败的 export
            pass
    return exports


def _build_export_ir(idx: int, export, result: "ParseResult") -> ExportIR:
    outer_resolved = _resolve_package_index(result, getattr(export, "outer_index", None))
    super_resolved = _resolve_package_index(result, getattr(export, "super_index", None))

    parent_class = None
    if result.blueprint and getattr(result.blueprint, "parent_class", None):
        parent_class = result.blueprint.parent_class

    properties = []
    for prop in getattr(export, "properties", None) or []:
        properties.append(_build_property_ir(prop))

    graphs = []
    for graph in getattr(export, "graphs", None) or []:
        graphs.append(_build_graph_ir(graph))

    bulk_data = getattr(export, "bulk_data_header", None)
    asset_type_data = getattr(export, "_asset_type_data", None)

    # 构建 UE 原始导出表字段
    raw = _build_export_raw_ir(export)

    return ExportIR(
        index=idx,
        object_name=_safe_str(getattr(export, "object_name", None)),
        object_class=_safe_str(getattr(export, "object_class", None)),
        serial_size=getattr(export, "serial_size", 0) or 0,
        outer_index_resolved=outer_resolved,
        super_index_resolved=super_resolved,
        parent_class=parent_class,
        properties=properties,
        graphs=graphs,
        bulk_data=bulk_data,
        asset_type_data=asset_type_data,
        parse_status=_safe_str(getattr(export, "parse_status", "success")) or "success",
        fallback_reason=(
            _safe_str(getattr(export, "fallback_reason", None))
            if getattr(export, "fallback_reason", None) is not None else None
        ),
        error_message=(
            _safe_str(getattr(export, "error_message", None))
            if getattr(export, "error_message", None) is not None else None
        ),
        ue_export_raw=raw,
        diagnostics=_build_export_diagnostics(export),
    )


def _build_export_raw_ir(export) -> ExportRawIR:
    """从 ObjectExport 构建 UE 原始导出表字段。"""

    def _pkg_index_raw(pi) -> int:
        """提取 PackageIndex 原始整数值。"""
        if pi is None:
            return 0
        return getattr(pi, "index", 0)

    return ExportRawIR(
        class_index=_pkg_index_raw(getattr(export, "class_index", None)),
        super_index=_pkg_index_raw(getattr(export, "super_index", None)),
        outer_index=_pkg_index_raw(getattr(export, "outer_index", None)),
        template_index=_pkg_index_raw(getattr(export, "template_index", None)),
        object_flags=getattr(export, "object_flags", 0) or 0,
        serial_offset=getattr(export, "serial_offset", 0) or 0,
        package_flags=getattr(export, "package_flags", 0) or 0,
        b_forced_export=bool(getattr(export, "b_forced_export", False)),
        b_not_for_client=bool(getattr(export, "b_not_for_client", False)),
        b_not_for_server=bool(getattr(export, "b_not_for_server", False)),
        b_is_inherited_instance=bool(getattr(export, "b_is_inherited_instance", False)),
        b_not_always_loaded_for_editor_game=bool(getattr(export, "b_not_always_loaded_for_editor_game", True)),
        b_is_asset=bool(getattr(export, "b_is_asset", False)),
        b_generate_public_hash=bool(getattr(export, "b_generate_public_hash", False)),
        script_serialization_start_offset=getattr(export, "script_serialization_start_offset", 0) or 0,
        script_serialization_end_offset=getattr(export, "script_serialization_end_offset", 0) or 0,
        guid=_safe_str(getattr(export, "guid", "")) or "",
    )


def _build_export_diagnostics(export) -> dict | None:
    """从 ObjectExport.transforms 构建诊断信息。"""
    transforms = getattr(export, "transforms", None) or {}
    if not transforms:
        return None
    return dict(transforms)


def _build_property_ir(prop) -> PropertyIR:
    return PropertyIR(
        name=_safe_str(getattr(prop, "name", None)),
        type=_safe_str(getattr(prop, "type", None)),
        value=getattr(prop, "value", None),
        array_index=getattr(prop, "array_index", -1) or -1,
        guid=_normalize_guid(getattr(prop, "guid", None)),
    )


def _resolve_package_index(result: "ParseResult", pkg_index) -> str | None:
    """将 PackageIndex 解析为可读路径字符串。"""
    if pkg_index is None or result.linker is None:
        return None
    try:
        obj_ref = result.linker.resolve_package_index(pkg_index)
        if obj_ref is None:
            return None
        # UObjectInstance 有 get_full_name() 方法
        if hasattr(obj_ref, "get_full_name"):
            return obj_ref.get_full_name()
        return str(obj_ref)
    except Exception:
        return None


def _build_resolved_depends_map(result: "ParseResult") -> list[list[dict]]:
    """将 DependsMap 的原始 PackageIndex 解析为可读路径。

    Returns:
        二维列表：外层按 export 索引，内层为 [{index, path}] 列表。
    """
    if not result.summary:
        return []
    raw_map = getattr(result.summary, "depends_map", None) or []
    if not raw_map:
        return []

    resolved: list[list[dict]] = []
    for dep_indices in raw_map:
        row: list[dict] = []
        for idx in dep_indices:
            pkg_idx = PackageIndex(idx)
            path = _resolve_package_index(result, pkg_idx)
            row.append({"index": idx, "path": path})
        resolved.append(row)
    return resolved


# 延迟导入避免循环：_build_graph_ir 定义在 _graphs.py 中
def _build_graph_ir(graph):
    from uasset_read.ir_builder._graphs import _build_graph_ir as _impl
    return _impl(graph)
