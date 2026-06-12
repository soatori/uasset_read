"""辅助表读取函数 — read_name_table, read_depends_map, read_soft_package_references, read_preload_dependencies。"""
from __future__ import annotations

import logging
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.exceptions import ParseError
from .models import PackageFileSummary

logger = logging.getLogger(__name__)


def read_name_table(archive: "FArchive", summary: PackageFileSummary) -> List[str]:
    """读取名称表。

    每个名称条目格式：
    - NameString (FString)
    - NonCasePreservingHash (uint16)
    - CasePreservingHash (uint16)
    """
    if summary.name_count <= 0:
        raise ParseError(
            f"name_count={summary.name_count}，UE 包必须有非空名称表"
        )

    if summary.name_offset <= 0:
        raise ParseError(
            f"name_offset={summary.name_offset} 无效，无法读取名称表"
        )

    try:
        archive.seek(summary.name_offset)
    except Exception as e:
        raise ParseError(
            f"seek({summary.name_offset}) 失败，无法读取名称表: {e}"
        ) from e

    name_map: List[str] = []
    for i in range(summary.name_count):
        try:
            name = archive.read_fstring()
            name_map.append(name)
            from uasset_read.constants import UE4_NAME_HASHES_SERIALIZED
            if summary.file_version_ue5 > 0 or summary.file_version_ue4 >= UE4_NAME_HASHES_SERIALIZED:
                archive.read(4)
        except Exception as e:
            logger.warning(
                "read_name_table: 读取名称条目 %d/%d 失败: %s（已读取 %d 个名称）",
                i, summary.name_count, e, len(name_map),
            )
            break

    if not name_map:
        raise ParseError(
            f"名称表为空（name_count={summary.name_count}, name_offset={summary.name_offset}），"
            f"无法继续解析"
        )

    return name_map


def read_depends_map(archive: "FArchive", summary: PackageFileSummary) -> List[List[int]]:
    """读取 DependsMap（依赖表）。

    UE 格式：TArray<TArray<FPackageIndex>>
    """
    if summary.depends_offset <= 0 or summary.export_count <= 0:
        return []

    archive.seek(summary.depends_offset)

    depends_map: List[List[int]] = []
    for _ in range(summary.export_count):
        dep_count = archive.read_i32()
        if dep_count < 0 or dep_count > 10000:
            logger.warning("DependsMap: 异常的依赖数量 %d, 跳过", dep_count)
            depends_map.append([])
            continue
        deps = []
        for _ in range(dep_count):
            deps.append(archive.read_i32())
        depends_map.append(deps)

    return depends_map


def read_soft_package_references(
    archive: "FArchive",
    summary: PackageFileSummary,
    name_map: List[str],
) -> List[str]:
    """读取 SoftPackageReferences（软包引用表）。"""
    if summary.soft_package_references_count <= 0 or summary.soft_package_references_offset <= 0:
        return []

    archive.seek(summary.soft_package_references_offset)

    refs: List[str] = []
    for _ in range(summary.soft_package_references_count):
        refs.append(archive.read_name(name_map))

    return refs


def read_preload_dependencies(archive: "FArchive", summary: PackageFileSummary) -> List[int]:
    """读取 PreloadDependencies（预加载依赖）。"""
    if summary.preload_dependency_offset <= 0 or summary.preload_dependency_count <= 0:
        return []

    archive.seek(summary.preload_dependency_offset)

    dependencies: List[int] = []
    for _ in range(summary.preload_dependency_count):
        dependencies.append(archive.read_i32())

    return dependencies
