"""主解析管线入口 — parse_uasset() 函数。

等价迁移 uasset_read.py §6223-6412。
Phase 33: 入口与测试适配。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List, Union

if TYPE_CHECKING:
    from uasset_read.link.linker import PackageLinker
    from uasset_read.kismet.result import KismetDecompiledResult

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


def _extract_kismet_decompiled(
    path: str,
    archive: FArchive,
    summary: "PackageFileSummary",
    name_map: List[str],
    import_map: List["ObjectImport"],
    export_map: List["ObjectExport"],
    tolerant: bool = True,
) -> List["KismetDecompiledResult"]:
    """Extract and decompile Kismet bytecode from Blueprint UStruct exports.

    Tolerant mode: failures return empty list for that function, never crash.
    Per D-10: Kismet decompilation failure does NOT block the main pipeline.
    """
    from uasset_read.kismet.bytecode_extractor import USTRUCT_TYPES, reset_bpgc_cache
    from uasset_read.serializers.object_resources import resolve_class_name
    from uasset_read.kismet.pipeline import decompile_single_function

    reset_bpgc_cache()

    results: List["KismetDecompiledResult"] = []
    for export in export_map:
        class_name = resolve_class_name(export.class_index, import_map, export_map)
        if class_name not in USTRUCT_TYPES:
            continue
        try:
            result = decompile_single_function(
                archive, export, summary, name_map, import_map, export_map,
                tolerant=tolerant,
            )
            if result is not None:
                results.append(result)
        except Exception:
            # Per D-10: failure does NOT block pipeline
            # Error logged to caller's warnings list
            pass
    return results


def _post_process(
    path: str,
    archive: FArchive,
    summary: "PackageFileSummary",
    name_map: List[str],
    import_map: List["ObjectImport"],
    export_map: List["ObjectExport"],
    result: "Union[ParseResult, LinkerParseResult]",
    tolerant: bool = True,
    linker: Optional["PackageLinker"] = None,
) -> None:
    """共享后处理：blueprint 元数据、图提取、依赖分析。

    通过 hasattr 守卫写入字段，同时支持 ParseResult 和 LinkerParseResult。
    """
    # Blueprint Graph 提取（先于元数据提取，以便传递 graphs 参数）
    graphs_list = None
    try:
        from uasset_read.graph import extract_blueprint_graphs
        if hasattr(result, 'graphs'):
            result.graphs = extract_blueprint_graphs(
                archive, summary, name_map, import_map, export_map,
            )
            graphs_list = result.graphs
    except ImportError:
        pass  # graph 模块不存在时静默跳过
    except ParseError as e:
        if hasattr(result, 'errors'):
            result.errors.append(f"graph extraction error: {e}")

    # Blueprint 元数据提取（使用 graphs 填充 functions）
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
                    linker=linker,
                    graphs=graphs_list,
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
            if linker is not None:
                from uasset_read.serializers.object_resources import detect_blueprint_with_linker
                is_bp = detect_blueprint_with_linker(export, linker)
            else:
                is_bp = detect_blueprint(export, import_map, export_map)
            if is_bp:
                temp_archive = FArchive(path, tolerant=tolerant)
                temp_archive.set_byte_swapping(archive._byte_swapping)
                try:
                    meta, warn = extract_blueprint_metadata(
                        export, temp_archive, import_map,
                        export_map, name_map, summary,
                        linker=linker,
                        graphs=graphs_list,
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

    # Kismet decompilation (Phase 64, per D-02, D-10)
    try:
        from uasset_read.kismet.pipeline import decompile_single_function
        if hasattr(result, 'decompiled_functions'):
            decompiled = _extract_kismet_decompiled(
                path, archive, summary, name_map,
                import_map, export_map, tolerant,
            )
            result.decompiled_functions = decompiled
            # If extraction produced errors that were caught internally,
            # and result has no decompiled functions but blueprint was found,
            # add a warning so the user knows decompilation was attempted
            if blueprint_metadata and not decompiled and hasattr(result, 'warnings'):
                result.warnings.append("Kismet decompilation: no functions decompiled (may have no bytecode)")
    except ImportError:
        pass  # kismet/pipeline.py does not exist yet — silent skip
    except Exception as e:
        if hasattr(result, 'warnings'):
            result.warnings.append(f"Kismet decompilation error: {e}")

    # Component property extraction (Phase 48)
    try:
        from uasset_read.blueprint.component_extractor import extract_components
        if hasattr(result, 'components'):
            result.components = extract_components(export_map, import_map)
    except ImportError:
        pass  # component_extractor module does not exist yet
    except Exception as e:
        if hasattr(result, 'errors'):
            result.errors.append(f"component extraction error: {e}")

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


def parse_uasset_with_linker(
    path: str,
    tolerant: bool = True,
    preload_all: bool = False,
) -> "LinkerParseResult":
    """使用 PackageLinker 的并行解析入口（D-01, D-04）。

    Args:
        path: .uasset 文件路径
        tolerant: 是否启用容错模式（默认开启）
        preload_all: 是否预加载所有 exports（默认 False，惰性加载）

    Returns:
        LinkerParseResult 实例（含对象图和后处理数据）
    """
    from uasset_read.link.linker import PackageLinker

    result = LinkerParseResult()
    archive = None

    try:
        archive = FArchive(path, tolerant=tolerant)

        # Extract mmap info
        mmap_info = archive.get_mmap_info()
        result.mmap_used = mmap_info["used"]
        result.mmap_warning = mmap_info["warning"]

        # 读取文件头
        result.summary = read_package_summary(archive)
        result.name_map = read_name_table(archive, result.summary)
        result.import_map = read_import_map(archive, result.summary, result.name_map)
        result.export_map = read_export_map(archive, result.summary, result.name_map)

        # 解析 ExportMap 属性
        for export in result.export_map:
            if export.serial_size > 0:
                try:
                    export.properties = parse_properties_from_export(
                        export, archive, result.summary, result.name_map,
                        result.export_map, result.import_map,
                        linker=result.linker,  # None at this point, linker not yet created
                    )
                except Exception as e:
                    result.errors.append(f"Property parse error in {export.object_name}: {e}")
                    export.properties = []

                # 提取组件变换属性
                if export.properties:
                    export.transforms = extract_component_transforms(export.properties)

        # 创建并运行 linker
        linker = PackageLinker(
            archive, result.summary, result.name_map,
            result.import_map, result.export_map,
        )
        linker.link()
        result.linker = linker
        result.all_objects = linker._import_objects + linker._export_objects
        result.root_objects = linker._root_objects

        # 可选：预加载所有 exports
        if preload_all:
            for i in range(len(linker._export_objects)):
                linker.preload(i)

        # 共享后处理
        _post_process(
            path, archive, result.summary, result.name_map,
            result.import_map, result.export_map, result, tolerant,
            linker=result.linker,
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
