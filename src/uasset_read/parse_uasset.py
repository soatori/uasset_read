"""主解析管线入口 — parse_uasset() 函数。

等价迁移 uasset_read.py §6223-6412。
Phase 33: 入口与测试适配。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List

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


def parse_uasset(path: str) -> ParseResult:
    """
    主入口：解析 .uasset 文件（D-08 优雅降级）。

    流程：
    1. 创建 FArchive
    2. 读取 PackageFileSummary
    3. 读取 NameMap
    4. 读取 ImportMap
    5. 读取 ExportMap
    6. 对每个 export 解析属性 + 提取组件变换
    7. 提取 Blueprint 元数据（BPGC 优先 → UBlueprint 回退）
    8. 提取 Blueprint Graphs（Phase 31）
    9. 依赖分析（imports, soft_references, circular_deps）

    错误处理：
    - VersionError: 返回 result.errors, result.is_success = False
    - ParseError: 返回部分结果 + 错误信息
    - Exception: 返回 Unexpected error

    Args:
        path: .uasset 文件路径

    Returns:
        ParseResult 实例（含解析数据和错误信息）
    """
    result = ParseResult()
    archive = None

    try:
        archive = FArchive(path)

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

        result.is_success = True

        # Blueprint 元数据提取
        blueprint_metadata = None
        asset_name = result.name_map[0] if result.name_map else None

        if asset_name:
            main_bpgc = find_main_blueprint_generated_class(
                result.export_map, result.import_map, asset_name
            )
            if main_bpgc:
                temp_archive = FArchive(path)
                temp_archive.set_byte_swapping(archive._byte_swapping)
                try:
                    meta, warn = extract_blueprint_metadata(
                        main_bpgc, temp_archive, result.import_map,
                        result.export_map, result.name_map, result.summary,
                    )
                    if meta:
                        blueprint_metadata = meta
                        if warn:
                            result.errors.append(f"blueprint parent warning: {warn}")
                except ParseError as e:
                    result.errors.append(f"blueprint extraction error (BPGC): {e}")
                finally:
                    temp_archive.close()

        # UBlueprint 回退
        if not blueprint_metadata:
            for export in result.export_map:
                if detect_blueprint(export, result.import_map, result.export_map):
                    temp_archive = FArchive(path)
                    temp_archive.set_byte_swapping(archive._byte_swapping)
                    try:
                        meta, warn = extract_blueprint_metadata(
                            export, temp_archive, result.import_map,
                            result.export_map, result.name_map, result.summary,
                        )
                        if meta:
                            blueprint_metadata = meta
                            if warn:
                                result.errors.append(f"blueprint parent warning: {warn}")
                    except ParseError as e:
                        result.errors.append(f"blueprint extraction error: {e}")
                    finally:
                        temp_archive.close()
                    break

        result.blueprint = blueprint_metadata

        # Blueprint Graph 提取（Phase 31 产出）
        try:
            from uasset_read.graph import extract_blueprint_graphs
            result.graphs = extract_blueprint_graphs(
                archive, result.summary, result.name_map,
                result.import_map, result.export_map,
            )
        except ImportError:
            result.graphs = []  # graph 模块不存在时静默跳过
        except ParseError as e:
            result.errors.append(f"graph extraction error: {e}")

        # 依赖分析（Phase 10）
        try:
            result.imports = build_imports_list(result.import_map)
            result.soft_references = read_soft_object_paths(
                archive, result.summary, result.name_map,
            )
            result.circular_deps = detect_circular_deps(result.import_map)
        except ParseError as e:
            result.errors.append(f"dependency analysis error: {e}")

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
