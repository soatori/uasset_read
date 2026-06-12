"""蓝图图解析入口 — 从 ExportMap 提取所有 EdGraph/UberEdGraph。

等价迁移 uasset_read.py L3095-3143。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Set

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import PKG_Cooked
from uasset_read.serializers.object_resources import get_asset_class
from uasset_read.serializers.graph import read_ue_graph
from uasset_read.models.core import UEdGraph

logger = logging.getLogger(__name__)

_KNOWN_GRAPH_NAMES: Set[str] = {
    "EventGraph", "Move", "UserConstructionScript", "AnimGraph",
    "UberGraph", "TransitionGraph", "ConduitGraph",
}


def _is_known_graph_export(export: "ObjectExport") -> bool:
    name = export.object_name or ""
    if name in _KNOWN_GRAPH_NAMES:
        return True
    if name.endswith("_GEN_VARIABLE") or name.endswith("_GEN_FUNC"):
        return True
    return False


def _has_k2node_children(
    export_idx: int,
    export_map: List["ObjectExport"],
    import_map: List["ObjectImport"],
) -> bool:
    one_based = export_idx + 1
    for child in export_map:
        if child.outer_index.index == one_based:
            child_name = child.object_name or ""
            if "K2Node" in child_name or "EdGraphNode" in child_name:
                return True
    return False


def extract_blueprint_graphs(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
) -> List[UEdGraph]:
    """
    从 ExportMap 提取蓝图图（等价迁移 uasset_read.py L3095-3143）。

    遍历 ExportMap，ClassIndex 解析后包含 "EdGraph" 或 "UberEdGraph" 的导出视为图对象。
    对每个图调用 read_ue_graph 完整解析 Graph→Node→Pin 三层结构。

    Fallback：当 class_index 未解析为 EdGraph 时，按名称模式或 K2Node 子导出检测。

    安全检查：PKG_Cooked 检查避免解析已剥离资产。
    """
    graphs: List[UEdGraph] = []

    is_cooked = (summary.package_flags & PKG_Cooked) != 0
    if is_cooked:
        return []

    for export_idx, export in enumerate(export_map):
        class_name = get_asset_class(export, import_map, export_map)
        is_graph = class_name in ('EdGraph', 'UberEdGraph')

        if not is_graph:
            if _is_known_graph_export(export) or _has_k2node_children(
                export_idx, export_map, import_map
            ):
                is_graph = True
                class_name = 'EdGraph'
                logger.debug(
                    "Graph fallback detected: export[%d] '%s' (class=%s) by name/children",
                    export_idx, export.object_name, class_name,
                )

        if is_graph:
            graph = read_ue_graph(
                archive, name_map, summary,
                export_map, import_map,
                export, class_name, export_idx + 1, linker
            )
            graphs.append(graph)

    return graphs
