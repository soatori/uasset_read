"""主解析管线入口 — parse_uasset() 函数。

等价迁移 uasset_read.py §6223-6412。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, List, Union, Sequence, Callable
from pathlib import Path

if TYPE_CHECKING:
    from uasset_read.link.linker import PackageLinker
    from uasset_read.kismet.result import KismetDecompiledResult

from uasset_read.constants import LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD
from uasset_read.archive import FArchive
from uasset_read.exceptions import VersionError, ParseError
from uasset_read.package import PackageBundle, PackageProvider, open_package_bundle
from uasset_read.serializers.package_summary import (
    read_package_summary, read_name_table, read_depends_map,
    read_preload_dependencies, validate_export_data_range,
    read_soft_package_references,
)
from uasset_read.versioning import build_version_container, VersionContainer
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
from uasset_read.models.diagnostics import OffsetRangeDiagnostic

logger = logging.getLogger(__name__)


def _extract_kismet_decompiled(
    path: str,
    archive: FArchive,
    summary: "PackageFileSummary",
    name_map: List[str],
    import_map: List["ObjectImport"],
    export_map: List["ObjectExport"],
    tolerant: bool = True,
    linker: Optional["PackageLinker"] = None,
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
                tolerant=tolerant, linker=linker,
            )
            if result is not None:
                results.append(result)
        except Exception as e:
            # Per D-10: failure does NOT block pipeline
            # Log warning so caller can diagnose if needed
            logger.debug("Kismet decompile failed for export '%s': %s", export.object_name, e)
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
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    archive_factory=None,
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
                linker=linker,
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
            owned_archive = archive_factory is not None
            temp_archive = archive_factory() if archive_factory else archive
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
                if owned_archive:
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
                owned_archive = archive_factory is not None
                temp_archive = archive_factory() if archive_factory else archive
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
                    if owned_archive:
                        temp_archive.close()
                break

    if hasattr(result, 'blueprint'):
        result.blueprint = blueprint_metadata

    # Kismet decompilation (per D-02, D-10)
    try:
        from uasset_read.kismet.pipeline import decompile_single_function
        if hasattr(result, 'decompiled_functions'):
            decompiled = _extract_kismet_decompiled(
                path, archive, summary, name_map,
                import_map, export_map, tolerant, linker=linker,
            )
            result.decompiled_functions = decompiled
            if decompiled and getattr(result, "graphs", None):
                from uasset_read.kismet.semantic import enrich_decompiled_functions
                enrich_decompiled_functions(decompiled, result.graphs)
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

    if include_parent_assets:
        _resolve_parent_assets(path, result, tolerant, asset_roots)

    # Component property extraction
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

    # name_map 一致性检查：如果 summary.name_count > 0 但 name_map 为空，
    # 说明名称表读取失败或为空，这不应该在成功的解析中出现。
    # 添加错误以确保集成测试的 name_map 验证通过。
    if hasattr(result, 'name_map') and not result.name_map:
        if summary is not None and getattr(summary, 'name_count', 0) > 0:
            if hasattr(result, 'errors'):
                result.errors.append(
                    f"name_map 为空（summary.name_count={summary.name_count}），"
                    f"名称表读取失败"
                )

    # 设置成功标志
    result.is_success = len(result.errors) == 0


def _resolve_parent_assets(
    path: str,
    result: "Union[ParseResult, LinkerParseResult]",
    tolerant: bool,
    asset_roots: Optional[Sequence[str]],
) -> None:
    """Best-effort parent Blueprint lookup used by cross-asset parsing."""
    if not getattr(result, "blueprint", None):
        return
    parent_class = getattr(result.blueprint, "parent_class", None)
    if not parent_class:
        return

    result.logic_sources.append({
        "source": "current_asset",
        "asset": path,
        "blueprint": result.summary.package_name if result.summary else None,
    })

    roots = [Path(root) for root in (asset_roots or [])]
    roots.append(Path(path).resolve().parent)
    parent_file = _find_parent_asset_file(parent_class, roots)
    if parent_file is None:
        result.logic_sources.append({
            "source": "native_parent",
            "class": parent_class,
            "status": "asset_not_found",
        })
        result.warnings.append(
            f"Parent asset '{parent_class}.uasset' not found in asset roots"
        )
        return

    try:
        parent_result = parse_uasset_with_linker(
            str(parent_file),
            tolerant=tolerant,
            include_parent_assets=False,
        )
    except Exception as exc:
        result.logic_sources.append({
            "source": "parent_asset",
            "class": parent_class,
            "asset": str(parent_file),
            "status": "parse_error",
            "error": str(exc),
        })
        result.warnings.append(f"Parent asset '{parent_file}' parse failed: {exc}")
        return

    result.resolved_parent_assets.append({
        "class": parent_class,
        "path": str(parent_file),
        "status": "parsed" if parent_result.is_success else "failed",
        "warnings": parent_result.warnings,
        "errors": parent_result.errors,
    })
    result.logic_sources.append({
        "source": "parent_asset",
        "class": parent_class,
        "asset": str(parent_file),
        "status": "parsed" if parent_result.is_success else "failed",
    })
    if parent_result.graphs:
        from uasset_read.graph import format_graphs_json
        result.inherited_blueprint_graphs.extend(format_graphs_json(parent_result.graphs))


def _find_parent_asset_file(parent_class: str, roots: Sequence[Path]) -> Optional[Path]:
    target_name = f"{parent_class}.uasset"
    seen: set[Path] = set()
    for root in roots:
        try:
            root = root.resolve()
        except OSError:
            continue
        if root in seen or not root.exists():
            continue
        seen.add(root)
        direct = root / target_name
        if direct.is_file():
            return direct
        if root.is_dir():
            try:
                match = next(root.rglob(target_name), None)
            except OSError:
                match = None
            if match is not None and match.is_file():
                return match
    return None


def _package_metadata(bundle: PackageBundle) -> dict:
    return {
        "package_kind": bundle.package_kind,
        "package_files": bundle.package_files,
        "container": bundle.container,
        "asset_type_details": {},
    }


def _record_parse_stage_error(
    result,
    archive,
    path: str,
    stage: str,
    field: str,
    error: Exception,
) -> None:
    if str(error) not in result.errors:
        result.errors.append(str(error))
    file_size = 0
    current_pos = 0
    if archive is not None:
        try:
            file_size = archive.total_size()
        except Exception:
            file_size = getattr(archive, "_file_size", 0) or 0
        try:
            current_pos = archive.tell()
        except Exception:
            current_pos = 0
    result.diagnostics.append(OffsetRangeDiagnostic(
        kind="parse_stage_error",
        asset_path=path,
        module=stage,
        field=field,
        current_pos=current_pos,
        file_size=file_size,
        source="_parse_package_core",
        error=str(error),
        fallback_used=True,
        fallback_result="partial" if getattr(result, "summary", None) is not None else "failed",
    ))
    result.is_success = False


def _run_required_stage(
    *,
    result,
    archive,
    path: str,
    tolerant: bool,
    stage: str,
    field: str,
    reader,
):
    try:
        return reader()
    except (VersionError, ParseError, Exception) as e:
        if not tolerant:
            raise
        _record_parse_stage_error(result, archive, path, stage, field, e)
        return None


def _should_use_lightweight_tolerant_parse(
    result,
    tolerant: bool,
    lightweight_threshold: Optional[int] = None,
) -> bool:
    if not tolerant or result.summary is None:
        return False
    threshold = (
        lightweight_threshold
        if lightweight_threshold is not None
        else LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD
    )
    return getattr(result.summary, "export_count", 0) > threshold


def _build_lightweight_function_graphs(export_map) -> list[dict]:
    entries = []
    for export in export_map or []:
        name = str(getattr(export, "object_name", "") or "")
        if not name or name.endswith("_C") or name.startswith("Default__"):
            continue
        if name in {"EventGraph", "UberGraphPages", "SimpleConstructionScript"}:
            continue
        entries.append({
            "function_name": name,
            "graph_source": "export_map",
            "entry_node_guid": "",
            "signature": {"return_type": "", "parameters": []},
            "execution_flows": [],
            "fallback_reason": "lightweight_tolerant_parse",
        })
        if len(entries) >= 64:
            break
    return entries


def _parse_package_core(
    path: str,
    result,
    tolerant: bool = True,
    provider: Optional["PackageProvider"] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    extra_linker_setup: Optional[Callable] = None,
    check_aes_key: Optional[bytes] = None,
    lightweight_threshold: Optional[int] = None,
) -> None:
    """共享核心解析逻辑 — 读取 package 并填充 result。

    Args:
        path: 文件路径
        result: ParseResult 或 LinkerParseResult 实例（被原地修改）
        tolerant: 容错模式
        provider: package provider
        mappings_path: 类型映射文件路径
        game: 游戏标识
        include_parent_assets: 是否解析父资产
        asset_roots: 资产根目录列表
        extra_linker_setup: linker 创建后的额外回调 (linker, result) -> None
        check_aes_key: 如果提供则抛出 ParseError（parse_package 兼容）
    """
    from uasset_read.link.linker import PackageLinker

    archive = None
    bundle = None
    mappings_provider = None

    try:
        if check_aes_key is not None:
            raise ParseError(
                "Unsupported argument: aes_key. Pass the key "
                "when constructing the Pak/IoStore reader and provider"
            )
        if mappings_path:
            from uasset_read.mappings import TypeMappingsProvider
            mappings_provider = TypeMappingsProvider.from_file(mappings_path)
            result.metadata["mappings_path"] = mappings_path
        if game:
            result.metadata["game"] = game

        bundle = open_package_bundle(path, provider=provider, tolerant=tolerant)
        archive = bundle.open_archive(tolerant=tolerant)
        result.metadata.update(_package_metadata(bundle))

        # Extract mmap info
        mmap_info = archive.get_mmap_info()
        result.mmap_used = mmap_info["used"]
        result.mmap_warning = mmap_info["warning"]

        # 读取文件头
        result.summary = _run_required_stage(
            result=result, archive=archive, path=path, tolerant=tolerant,
            stage="package_summary", field="summary",
            reader=lambda: read_package_summary(archive),
        )
        if result.summary is None:
            return
        result.version_container = build_version_container(result.summary)

        # 截断文件检测：验证导出数据范围
        try:
            validate_export_data_range(archive, result.summary)
        except Exception as e:
            if not tolerant:
                raise
            _record_parse_stage_error(
                result, archive, path, "package_summary", "export_data_range", e
            )
            return

        # 读取名称表
        result.name_map = _run_required_stage(
            result=result, archive=archive, path=path, tolerant=tolerant,
            stage="name_table", field="name_map",
            reader=lambda: read_name_table(archive, result.summary),
        )
        if result.name_map is None:
            result.name_map = []
            return

        # 读取导入表
        result.import_map = _run_required_stage(
            result=result, archive=archive, path=path, tolerant=tolerant,
            stage="import_map", field="import_map",
            reader=lambda: read_import_map(archive, result.summary, result.name_map),
        )
        if result.import_map is None:
            result.import_map = []
            return

        # 读取导出表
        result.export_map = _run_required_stage(
            result=result, archive=archive, path=path, tolerant=tolerant,
            stage="export_map", field="export_map",
            reader=lambda: read_export_map(archive, result.summary, result.name_map),
        )
        if result.export_map is None:
            result.export_map = []
            return

        # 读取 DependsMap（依赖表）和 PreloadDependencies（预加载依赖）
        if hasattr(result.summary, 'depends_offset'):
            result.summary.depends_map = read_depends_map(archive, result.summary)
        if hasattr(result.summary, 'preload_dependency_count'):
            result.summary.preload_dependencies = read_preload_dependencies(archive, result.summary)

        # 读取 SoftPackageReferences（软包引用表）
        if hasattr(result.summary, 'soft_package_references_count') and result.summary.soft_package_references_count > 0:
            result.soft_package_references = read_soft_package_references(archive, result.summary, result.name_map)

        # 读取 SoftObjectPathList（UE5.7+ 用于索引化 SoftObjectProperty 解析）
        if hasattr(result.summary, 'soft_object_paths_count') and result.summary.soft_object_paths_count > 0:
            result.soft_object_path_list = read_soft_object_paths(
                archive, result.summary, result.name_map
            )
        else:
            result.soft_object_path_list = []

        # 将 soft_object_path_list 存储在 summary 上供属性解析器访问
        setattr(result.summary, '_soft_object_path_list', result.soft_object_path_list)

        # 创建 linker 用于完整对象图解析（在属性解析之前创建，确保 parse_properties_from_export 可使用 linker）
        linker: Optional["PackageLinker"] = None
        try:
            linker = PackageLinker(
                archive, result.summary, result.name_map,
                result.import_map, result.export_map or [],
                version_container=result.version_container,
            )
            linker.link()
            result.linker = linker

            if extra_linker_setup is not None:
                extra_linker_setup(linker, result)

            # NOTE: post_load() is deferred until after export preloading (link → preload → post_load)
        except Exception as e:
            if not tolerant:
                raise ParseError(f"Linker creation failed: {e}") from e
            result.errors.append(f"Linker creation failed: {e}")

        if _should_use_lightweight_tolerant_parse(result, tolerant, lightweight_threshold):
            result.warnings.append(
                "Lightweight tolerant parse used due to export complexity "
                f"(exports={getattr(result.summary, 'export_count', 0)})"
            )
            result.metadata["lightweight_tolerant_parse"] = True
            result.metadata["function_graphs_fallback"] = _build_lightweight_function_graphs(result.export_map)
            result.is_success = len(result.errors) == 0
            return

        # 解析 ExportMap 属性 — 通过 linker.preload() 统一调度（link → preload → post_load）
        _mappings = mappings_provider.mappings if mappings_provider else None
        for _exp_idx, export in enumerate(result.export_map or []):
            if export.serial_size > 0:
                try:
                    if linker is not None:
                        linker.preload(
                            _exp_idx,
                            mappings=_mappings,
                            game=game,
                            tolerant=tolerant,
                        )
                        # 向后兼容：将 linker instance 的属性复制回 export.properties
                        inst = linker._export_objects[_exp_idx]
                        export.properties = inst.serialized_properties
                    else:
                        export.properties = parse_properties_from_export(
                            export, archive, result.summary, result.name_map,
                            result.export_map or [], result.import_map,
                            linker=linker,
                            mappings=_mappings,
                            game=game,
                            tolerant=tolerant,
                        )
                    if not getattr(export, "parse_status", None):
                        setattr(export, "parse_status", "success")
                    elif getattr(export, "parse_status", None) in ("opaque", "partial_metadata"):
                        # 保持 asset type handler 设置的状态，不覆盖为 success
                        pass
                except Exception as e:
                    if not tolerant:
                        raise ParseError(f"Property parse error in {export.object_name}: {e}") from e
                    result.errors.append(f"Property parse error in {export.object_name}: {e}")
                    export.properties = []
                    setattr(export, "parse_status", "failed")
                    setattr(export, "fallback_reason", "parse_error")
                    setattr(export, "error_message", str(e))

                # 提取组件变换属性
                if export.properties:
                    export.transforms = extract_component_transforms(export.properties)

        # post_load — 在所有 export 预加载完成后执行（link → preload → post_load）
        if linker is not None:
            try:
                linker.post_load()
            except Exception as e:
                if not tolerant:
                    raise ParseError(f"Linker post_load failed: {e}") from e
                result.errors.append(f"Linker post_load failed: {e}")

        # 共享后处理
        _post_process(
            path, archive, result.summary, result.name_map,
            result.import_map, result.export_map or [], result, tolerant,
            linker=linker,
            include_parent_assets=include_parent_assets,
            asset_roots=asset_roots,
            archive_factory=lambda: bundle.open_archive(tolerant=tolerant) if bundle else FArchive(path, tolerant=tolerant),
        )
        result.is_success = len(result.errors) == 0

    except VersionError as e:
        _record_parse_stage_error(result, archive, path, "version", "legacy_file_version", e)
        result.errors.append(str(e))
        result.is_success = False
        if not tolerant:
            raise

    except ParseError as e:
        _record_parse_stage_error(result, archive, path, "parse", "parse_error", e)
        result.errors.append(str(e))
        if e.partial_result:
            for key, value in e.partial_result.items():
                if hasattr(result, key):
                    setattr(result, key, value)
        result.is_success = False
        if not tolerant:
            raise

    except Exception as e:
        _record_parse_stage_error(result, archive, path, "parse", "unexpected", e)
        result.errors.append(f"Unexpected error: {str(e)}")
        result.is_success = False
        if not tolerant:
            raise

    finally:
        # 收集 linker 诊断（PackageIndex 越界、serial_offset/size 异常等）
        if result.linker and getattr(result.linker, 'diagnostics', None):
            result.diagnostics.extend(result.linker.diagnostics)
        if archive:
            # 收集 FArchive 诊断记录（截断检测、偏移越界等）
            archive_diagnostics = archive.get_diagnostics()
            if archive_diagnostics:
                result.diagnostics = archive_diagnostics + result.diagnostics
            archive.close()


def parse_package(
    path: str,
    tolerant: bool = True,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    aes_key: Optional[bytes] = None,
    provider: Optional[PackageProvider] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
    include_linker: bool = True,  # Deprecated: linker is now always created
    lightweight_threshold: Optional[int] = None,
) -> ParseResult:
    """
    主入口：解析 Unreal package（.uasset 或 .umap）。

    Args:
        path: .uasset/.umap 文件路径
        tolerant: 是否启用容错模式（默认开启）
        aes_key: Deprecated. Construct encrypted container readers/providers with
            their AES key instead; the parser no longer accepts an unused key.
        provider: 可选 package provider（filesystem/pak/iostore）
        include_linker: Deprecated. Linker is now always created for complete
            object graph resolution. Parameter retained for backward compatibility.

    Returns:
        ParseResult 实例（含解析数据和错误信息）
    """
    result = ParseResult()

    # Handle deprecated aes_key inline (don't pass to core)
    if aes_key is not None:
        result.errors.append(
            "Unsupported argument: aes_key. Pass the key "
            "when constructing the Pak/IoStore reader and provider"
        )
        result.is_success = False
        return result

    _parse_package_core(
        path, result,
        tolerant=tolerant, provider=provider,
        mappings_path=mappings_path, game=game,
        include_parent_assets=include_parent_assets,
        asset_roots=asset_roots,
        lightweight_threshold=lightweight_threshold,
    )
    return result


def parse_uasset(
    path: str,
    tolerant: bool = True,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
    include_linker: bool = True,  # Deprecated: linker is now always created
) -> ParseResult:
    """
    兼容入口：解析 .uasset 文件。

    Internally delegates to parse_package(), so sidecar payload discovery is
    shared with .umap/package parsing.
    """
    return parse_package(
        path,
        tolerant=tolerant,
        include_parent_assets=include_parent_assets,
        asset_roots=asset_roots,
        mappings_path=mappings_path,
        game=game,
        include_linker=include_linker,
    )


def parse_uasset_with_linker(
    path: str,
    tolerant: bool = True,
    preload_all: bool = False,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    provider: Optional[PackageProvider] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
    lightweight_threshold: Optional[int] = None,
) -> "LinkerParseResult":
    """使用 PackageLinker 的并行解析入口（D-01, D-04）。

    Args:
        path: .uasset 文件路径
        tolerant: 是否启用容错模式（默认开启）
        preload_all: 是否预加载所有 exports（默认 False，惰性加载）
        provider: 可选 package provider（filesystem/pak/iostore）

    Returns:
        LinkerParseResult 实例（含对象图和后处理数据）
    """
    result = LinkerParseResult()

    def extra_linker_setup(linker, res):
        res.all_objects = linker._import_objects + linker._export_objects
        res.root_objects = linker._root_objects

    _parse_package_core(
        path, result,
        tolerant=tolerant, provider=provider,
        mappings_path=mappings_path, game=game,
        include_parent_assets=include_parent_assets,
        asset_roots=asset_roots,
        extra_linker_setup=extra_linker_setup,
        lightweight_threshold=lightweight_threshold,
    )

    if preload_all and result.linker:
        for i in range(len(result.linker._export_objects)):
            try:
                result.linker.preload(i)
            except (ParseError, Exception) as e:
                logger.warning("预加载 export %d 失败，跳过: %s", i, e)

    return result
