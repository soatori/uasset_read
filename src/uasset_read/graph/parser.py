"""蓝图图解析入口 — 从 ExportMap 提取所有 EdGraph/UberEdGraph。

等价迁移 uasset_read.py L3095-3143。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import PKG_Cooked
from uasset_read.serializers.object_resources import get_asset_class
from uasset_read.serializers.graph import read_ue_graph
from uasset_read.models.core import UEdGraph


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

    安全检查：PKG_Cooked 检查避免解析已剥离资产。

    Args:
        archive: FArchive 二进制读取器
        summary: PackageFileSummary 包含 package_flags
        name_map: 名称表列表
        import_map: 导入表列表（用于 ClassIndex 解析）
        export_map: 导出表列表（用于 ClassIndex 解析）

    Returns:
        List[UEdGraph]: 检测到的图列表
    """
    graphs: List[UEdGraph] = []

    # PKG_Cooked 检查 — cooked 资产无图数据
    is_cooked = (summary.package_flags & PKG_Cooked) != 0
    if is_cooked:
        return []

    # 遍历 ExportMap 寻找 EdGraph/UberEdGraph 类型导出
    for export_idx, export in enumerate(export_map):
        class_name = get_asset_class(export, import_map, export_map)

        if class_name and class_name in ('EdGraph', 'UberEdGraph'):
            graph = read_ue_graph(
                archive, name_map, summary,
                export_map, import_map,
                export, class_name, export_idx + 1, linker  # 1-based index
            )
            graphs.append(graph)

    return graphs
