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

import logging

from uasset_read.constants import PKG_Cooked
from uasset_read.serializers.object_resources import get_asset_class
from uasset_read.serializers.graph import read_ue_graph
from uasset_read.models.core import UEdGraph

logger = logging.getLogger(__name__)


def _validate_graph_export_offset(export, archive_size: int) -> bool:
    """验证图 export 的序列化偏移是否在有效范围内。

    当 serial_offset 为 0 且 serial_size > 0 时，偏移异常（非 Default__ export）。
    当 serial_offset + serial_size 超出 archive 边界时，数据截断。

    Args:
        export: ObjectExport 实例
        archive_size: 归档文件总大小（字节）

    Returns:
        True 表示偏移有效，可安全读取
    """
    serial_offset = getattr(export, "serial_offset", 0)
    serial_size = getattr(export, "serial_size", 0)

    if serial_size == 0:
        return True  # 空 export 跳过检查

    # 偏移不应为 0（除非是特殊 Default__ export）
    if serial_offset == 0 and not str(getattr(export, "object_name", "")).startswith("Default__"):
        logger.warning(
            "图 export '%s' serial_offset=0 且 serial_size=%d，偏移异常",
            export.object_name, serial_size,
        )
        return False

    # 检查是否超出归档边界
    if archive_size > 0 and serial_offset + serial_size > archive_size:
        logger.warning(
            "图 export '%s' 偏移越界: offset=%d + size=%d > archive_size=%d",
            export.object_name, serial_offset, serial_size, archive_size,
        )
        return False

    return True


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

    # 获取 archive 大小用于偏移验证
    archive_size = 0
    if archive is not None:
        try:
            archive_size = archive.total_size()
        except (OSError, AttributeError):
            archive_size = 0

    # 遍历 ExportMap 寻找 EdGraph/UberEdGraph 类型导出
    for export_idx, export in enumerate(export_map):
        class_name = get_asset_class(export, import_map, export_map)

        if class_name and class_name in ('EdGraph', 'UberEdGraph'):
            # 验证图 export 偏移在有效范围内
            if not _validate_graph_export_offset(export, archive_size):
                logger.warning(
                    "跳过图 export '%s'（偏移验证失败）",
                    export.object_name,
                )
                continue

            graph = read_ue_graph(
                archive, name_map, summary,
                export_map, import_map,
                export, class_name, export_idx + 1, linker  # 1-based index
            )
            graphs.append(graph)

    return graphs
