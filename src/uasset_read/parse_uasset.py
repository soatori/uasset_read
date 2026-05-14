"""主解析管线入口 — parse_uasset() 函数。

等价迁移 uasset_read.py §6223-6412。
Phase 33: 入口与测试适配。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List, Union

from uasset_read.archive import FArchive
from uasset_read.exceptions import VersionError, ParseError
from uasset_read.serializers.package_summary import read_package_summary, read_name_table
from uasset_read.serializers.object_resources import (
    read_import_map, read_export_map,
    find_main_blueprint_generated_class, detect_blueprint,
    build_imports_list, read_soft_object_paths, detect_circular_deps,
)
from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.blueprint import (
    extract_blueprint_metadata,
    extract_component_transforms,
)
from uasset_read.models.result import ParseResult
from uasset_read.link.result import LinkerParseResult


def _post_process(
    path: str,
    archive: FArchive,
    summary: "PackageFileSummary",
    name_map: List[str],
    import_map: List["ObjectImport"],
    export_map: List["ObjectExport"],
    result: "Union[ParseResult, LinkerParseResult]",
    tolerant: bool = True,
) -> None:
    """共享后处理：blueprint 元数据、图提取、依赖分析。

    通过 hasattr 守卫写入字段，同时支持 ParseResult 和 LinkerParseResult。
    """
    # Blueprint 元数据提取
    blueprint_metadata = None
    asset_name = name_map[0] if name_map else None

    if asset_name:
        main_bpgc = find_main_blueprint_generated_class(
            export_map, import_map, asset_name
        )
        if main_bpgc:
            temp_archive = FArchive(path, tolerant=tolerant)
            temp_archive.set_byte_swapping(archive._byte_swapping)
            try:
                meta, warn = extract_blueprint_metadata(
                    main_bpgc, temp_archive, import_map,
                    export_map, name_map, summary,
                )
                if meta:
                    blueprint_metadata = meta
                    if hasattr(result, 'errors') and warn:
                        result.errors.append(f"blueprint parent warning: {warn}")
            except ParseError as e:
                if hasattr(result, 'errors'):
                    result.errors.append(f"blueprint extraction error (BPGC): {e}")
            finally:
                temp_archive.close()

    # UBlueprint 回退
    if not blueprint_metadata:
        for export in export_map:
            if detect_blueprint(export, import_map, export_map):
                temp_archive = FArchive(path, tolerant=tolerant)
                temp_archive.set_byte_swapping(archive._byte_swapping)
                try:
                    meta, warn = extract_blueprint_metadata(
                        export, temp_archive, import_map,
                        export_map, name_map, summary,
                    )
                    if meta:
                        blueprint_metadata = meta
                        if hasattr(result, 'errors') and warn:
                            result.errors.append(f"blueprint parent warning: {warn}")
                except ParseError as e:
                    if hasattr(result, 'errors'):
                        result.errors.append(f"blueprint extraction error: {e}")
                finally:
                    temp_archive.close()
                break

    if hasattr(result, 'blueprint'):
        result.blueprint = blueprint_metadata

    # Blueprint Graph 提取
    try:
        from uasset_read.graph import extract_blueprint_graphs
        if hasattr(result, 'graphs'):
            result.graphs = extract_blueprint_graphs(
                archive, summary, name_map, import_map, export_map,
            )
    except ImportError:
        pass  # graph 模块不存在时静默跳过
    except ParseError as e:
        if hasattr(result, 'errors'):
            result.errors.append(f"graph extraction error: {e}")

    # 依赖分析
    try:
        if hasattr(result, 'imports'):
            result.imports = build_imports_list(import_map)
        if hasattr(result, 'soft_references'):
            result.soft_references = read_soft_object_paths(
                archive, summary, name_map,
            )
        if hasattr(result, 'circular_deps'):
            result.circular_deps = detect_circular_deps(import_map)
    except ParseError as e:
        if hasattr(result, 'errors'):
            result.errors.append(f"dependency analysis error: {e}")

    # 设置成功标志
    result.is_success = len(result.errors) == 0


def parse_uasset(path: str, tolerant: bool = True) -> ParseResult:
    """
    主入口：解析 .uasset 文件（D-08 优雅降级）。

    Args:
        path: .uasset 文件路径
        tolerant: 是否启用容错模式（默认开启）

    Returns:
        ParseResult 实例（含解析数据和错误信息）
    """
    result = ParseResult()
    archive = None

    try:
        archive = FArchive(path, tolerant=tolerant)

        # Extract mmap info
        mmap_info = archive.get_mmap_info()
        result.mmap_used = mmap_info["used"]
        result.mmap_warning = mmap_info["warning"]

        # 读取文件头
        result.summary = read_package_summary(archive)

        # 读取名称表
        result.name_map = read_name_table(archive, result.summary)

        # 读取导入表
        result.import_map = read_import_map(archive, result.summary, result.name_map)

        # 读取导出表
        result.export_map = read_export_map(archive, result.summary, result.name_map)

        # 解析 ExportMap 属性
        for export in result.export_map:
            if export.serial_size > 0:
                try:
                    export.properties = parse_properties_from_export(
                        export, archive, result.summary, result.name_map,
                        result.export_map, result.import_map,
                    )
                except Exception as e:
                    result.errors.append(f"Property parse error in {export.object_name}: {e}")
                    export.properties = []

                # 提取组件变换属性
                if export.properties:
                    export.transforms = extract_component_transforms(export.properties)

        # 共享后处理
        _post_process(
            path, archive, result.summary, result.name_map,
            result.import_map, result.export_map, result, tolerant,
        )

    except VersionError as e:
        result.errors.append(str(e))
        result.is_success = False

    except ParseError as e:
        result.errors.append(str(e))
        if e.partial_result:
            for key, value in e.partial_result.items():
                if hasattr(result, key):
                    setattr(result, key, value)
        result.is_success = False

    except Exception as e:
        result.errors.append(f"Unexpected error: {str(e)}")
        result.is_success = False

    finally:
        if archive:
            archive.close()

    return result
