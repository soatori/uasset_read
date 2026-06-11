"""主解析管线入口 — parse_uasset() 函数。

等价迁移 uasset_read.py §6223-6412。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, List, Union, Sequence, Callable
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
from uasset_read.versioning import build_version_container
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
    # 关键发现：NewVariables 属性存储在 UBlueprint export（蓝图资产本身）
    # 而非 BlueprintGeneratedClass export（生成的类实例）
    # 参考 UE 源码：UBlueprint::Serialize() 中 NewVariables 是 UPROPERTY
    blueprint_metadata = None
    asset_name = name_map[0] if name_map else None

    # 首先查找 UBlueprint export（包含 NewVariables）
    main_blueprint = None
    if asset_name:
        # 查找主 Blueprint export（名称匹配 asset_name，不含 "_C"）
        for export in export_map:
            is_bp = detect_blueprint(export, import_map, export_map) if import_map else False
            if is_bp and export.object_name:
                simple_asset_name = asset_name.split("/")[-1] if "/" in asset_name else asset_name
                if export.object_name == simple_asset_name:
                    main_blueprint = export
                    break

    if main_blueprint:
        owned_archive = archive_factory is not None
        temp_archive = archive_factory() if archive_factory else archive
        temp_archive.set_byte_swapping(archive._byte_swapping)
        try:
            meta, warn = extract_blueprint_metadata(
                main_blueprint, temp_archive, import_map,
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

    # BPGC 回退（不包含 NewVariables，仅用于获取 ParentClass 等元数据）
    if not blueprint_metadata and asset_name:
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
        from uasset_read.blueprint.component_extractor import extract_components, extract_scs_tree
        if hasattr(result, 'components'):
            result.components = extract_components(export_map, import_map)
        # SCS 组件树提取 (Issue #70)
        try:
            scs_tree = extract_scs_tree(
                export_map, import_map,
                archive=archive, summary=summary, name_map=name_map,
            )
            if scs_tree and hasattr(result, 'metadata'):
                result.metadata["scs_tree"] = scs_tree
        except Exception as e:
            if hasattr(result, 'warnings'):
                result.warnings.append(f"SCS tree extraction error: {e}")
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


@dataclass
class _ParseContext:
    """解析管线上下文 — 在各 stage 之间传递状态。"""
    path: str
    result: Any
    tolerant: bool = True
    provider: Any = None
    mappings_path: Optional[str] = None
    game: Optional[str] = None
    include_parent_assets: bool = False
    asset_roots: Optional[Sequence[str]] = None
    extra_linker_setup: Optional[Callable] = None
    lightweight_threshold: Optional[int] = None
    bundle: Any = None
    archive: Any = None
    mappings_provider: Any = None
    linker: Any = None
    aborted: bool = False

    def abort(self) -> None:
        self.aborted = True


def _stage_open_bundle_and_archive(ctx: _ParseContext) -> None:
    """Stage 1: 打开 mappings、bundle、archive，提取 mmap 信息。"""
    if ctx.mappings_path:
        from uasset_read.mappings import TypeMappingsProvider
        ctx.mappings_provider = TypeMappingsProvider.from_file(ctx.mappings_path)
        ctx.result.metadata["mappings_path"] = ctx.mappings_path
    if ctx.game:
        ctx.result.metadata["game"] = ctx.game

    ctx.bundle = open_package_bundle(ctx.path, provider=ctx.provider, tolerant=ctx.tolerant)
    ctx.archive = ctx.bundle.open_archive(tolerant=ctx.tolerant)
    ctx.result.metadata.update(_package_metadata(ctx.bundle))

    # Extract mmap info
    mmap_info = ctx.archive.get_mmap_info()
    ctx.result.mmap_used = mmap_info["used"]
    ctx.result.mmap_warning = mmap_info["warning"]


def _stage_build_parse_context(ctx: _ParseContext) -> None:
    """Stage 2: 设置引擎家族、版本配置、验证导出数据范围。"""
    # 设置引擎家族和版本配置（UE4/UE5 兼容性）
    file_version_ue5 = getattr(ctx.result.summary, 'file_version_ue5', 0)
    legacy_file_version = getattr(ctx.result.summary, 'legacy_file_version', -9)
    file_version_ue4 = getattr(ctx.result.summary, 'file_version_ue4', 0)

    if file_version_ue5 == 0 and legacy_file_version > -6:
        ctx.result.engine_family = "ue4"
        ctx.result.compatibility_mode = "compatibility"
    else:
        ctx.result.engine_family = "ue5"
        ctx.result.compatibility_mode = "native"

    # 构建版本配置
    from uasset_read.package_version_profile import build_version_profile
    ctx.result.version_profile = build_version_profile(
        legacy_file_version=legacy_file_version,
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5,
    )

    ctx.result.version_container = build_version_container(ctx.result.summary)

    # 截断文件检测：验证导出数据范围
    try:
        validate_export_data_range(ctx.archive, ctx.result.summary)
    except Exception as e:
        if not ctx.tolerant:
            raise
        _record_parse_stage_error(
            ctx.result, ctx.archive, ctx.path, "package_summary", "export_data_range", e
        )
        ctx.abort()


def _stage_read_core_tables(ctx: _ParseContext) -> None:
    """Stage 3: 读取 name_map, import_map, export_map, depends, soft refs。"""
    # 读取名称表
    ctx.result.name_map = _run_required_stage(
        result=ctx.result, archive=ctx.archive, path=ctx.path, tolerant=ctx.tolerant,
        stage="name_table", field="name_map",
        reader=lambda: read_name_table(ctx.archive, ctx.result.summary),
    )
    if ctx.result.name_map is None:
        ctx.result.name_map = []
        ctx.abort()
        return

    # 读取导入表
    ctx.result.import_map = _run_required_stage(
        result=ctx.result, archive=ctx.archive, path=ctx.path, tolerant=ctx.tolerant,
        stage="import_map", field="import_map",
        reader=lambda: read_import_map(ctx.archive, ctx.result.summary, ctx.result.name_map),
    )
    if ctx.result.import_map is None:
        ctx.result.import_map = []
        ctx.abort()
        return

    # 读取导出表
    ctx.result.export_map = _run_required_stage(
        result=ctx.result, archive=ctx.archive, path=ctx.path, tolerant=ctx.tolerant,
        stage="export_map", field="export_map",
        reader=lambda: read_export_map(ctx.archive, ctx.result.summary, ctx.result.name_map),
    )
    if ctx.result.export_map is None:
        ctx.result.export_map = []
        ctx.abort()
        return

    # 读取 DependsMap（依赖表）和 PreloadDependencies（预加载依赖）
    if hasattr(ctx.result.summary, 'depends_offset'):
        ctx.result.summary.depends_map = read_depends_map(ctx.archive, ctx.result.summary)
    if hasattr(ctx.result.summary, 'preload_dependency_count'):
        ctx.result.summary.preload_dependencies = read_preload_dependencies(ctx.archive, ctx.result.summary)

    # 读取 SoftPackageReferences（软包引用表）
    if hasattr(ctx.result.summary, 'soft_package_references_count') and ctx.result.summary.soft_package_references_count > 0:
        ctx.result.soft_package_references = read_soft_package_references(ctx.archive, ctx.result.summary, ctx.result.name_map)

    # 读取 SoftObjectPathList（UE5.7+ 用于索引化 SoftObjectProperty 解析）
    if hasattr(ctx.result.summary, 'soft_object_paths_count') and ctx.result.summary.soft_object_paths_count > 0:
        ctx.result.soft_object_path_list = read_soft_object_paths(
            ctx.archive, ctx.result.summary, ctx.result.name_map
        )
    else:
        ctx.result.soft_object_path_list = []

    # 将 soft_object_path_list 存储在 summary 上供属性解析器访问
    setattr(ctx.result.summary, '_soft_object_path_list', ctx.result.soft_object_path_list)


def _stage_create_and_link_linker(ctx: _ParseContext) -> None:
    """Stage 4: 创建 PackageLinker，执行 link() 和 extra_linker_setup。"""
    try:
        from uasset_read.link.linker import PackageLinker
        ctx.linker = PackageLinker(
            ctx.archive, ctx.result.summary, ctx.result.name_map,
            ctx.result.import_map, ctx.result.export_map or [],
            version_container=ctx.result.version_container,
        )
        ctx.linker.link()
        ctx.result.linker = ctx.linker

        if ctx.extra_linker_setup is not None:
            ctx.extra_linker_setup(ctx.linker, ctx.result)

        # NOTE: post_load() is deferred until after export preloading (link → preload → post_load)
    except Exception as e:
        if not ctx.tolerant:
            raise ParseError(f"Linker creation failed: {e}") from e
        ctx.result.errors.append(f"Linker creation failed: {e}")


def _stage_preload_exports(ctx: _ParseContext) -> None:
    """Stage 5: 预加载 export 属性（linker.preload 或 parse_properties_from_export）。"""
    if _should_use_lightweight_tolerant_parse(ctx.result, ctx.tolerant, ctx.lightweight_threshold):
        ctx.result.warnings.append(
            "Lightweight tolerant parse used due to export complexity "
            f"(exports={getattr(ctx.result.summary, 'export_count', 0)})"
        )
        ctx.result.metadata["lightweight_tolerant_parse"] = True
        ctx.result.metadata["function_graphs_fallback"] = _build_lightweight_function_graphs(ctx.result.export_map)
        ctx.result.is_success = len(ctx.result.errors) == 0
        ctx.abort()
        return

    # 解析 ExportMap 属性 — 通过 linker.preload() 统一调度（link → preload → post_load）
    _mappings = ctx.mappings_provider.mappings if ctx.mappings_provider else None
    for _exp_idx, export in enumerate(ctx.result.export_map or []):
        if export.serial_size > 0:
            try:
                if ctx.linker is not None:
                    ctx.linker.preload(
                        _exp_idx,
                        mappings=_mappings,
                        game=ctx.game,
                        tolerant=ctx.tolerant,
                    )
                    # 向后兼容：将 linker instance 的属性复制回 export.properties
                    inst = ctx.linker._export_objects[_exp_idx]
                    export.properties = inst.serialized_properties
                else:
                    export.properties = parse_properties_from_export(
                        export, ctx.archive, ctx.result.summary, ctx.result.name_map,
                        ctx.result.export_map or [], ctx.result.import_map,
                        linker=ctx.linker,
                        mappings=_mappings,
                        game=ctx.game,
                        tolerant=ctx.tolerant,
                    )
                if not getattr(export, "parse_status", None):
                    setattr(export, "parse_status", "success")
                elif getattr(export, "parse_status", None) in ("opaque", "partial_metadata"):
                    # 保持 asset type handler 设置的状态，不覆盖为 success
                    pass
            except Exception as e:
                if not ctx.tolerant:
                    raise ParseError(f"Property parse error in {export.object_name}: {e}") from e
                ctx.result.errors.append(f"Property parse error in {export.object_name}: {e}")
                export.properties = []
                setattr(export, "parse_status", "failed")
                setattr(export, "fallback_reason", "parse_error")
                setattr(export, "error_message", str(e))

            # 提取组件变换属性
            if export.properties:
                export.transforms = extract_component_transforms(export.properties)


def _stage_run_post_load_and_post_process(ctx: _ParseContext) -> None:
    """Stage 6: 执行 post_load 和 _post_process。"""
    # post_load — 在所有 export 预加载完成后执行（link → preload → post_load）
    if ctx.linker is not None:
        try:
            ctx.linker.post_load()
        except Exception as e:
            if not ctx.tolerant:
                raise ParseError(f"Linker post_load failed: {e}") from e
            ctx.result.errors.append(f"Linker post_load failed: {e}")

    # 共享后处理
    _post_process(
        ctx.path, ctx.archive, ctx.result.summary, ctx.result.name_map,
        ctx.result.import_map, ctx.result.export_map or [], ctx.result, ctx.tolerant,
        linker=ctx.linker,
        include_parent_assets=ctx.include_parent_assets,
        asset_roots=ctx.asset_roots,
        archive_factory=lambda: ctx.bundle.open_archive(tolerant=ctx.tolerant) if ctx.bundle else FArchive(ctx.path, tolerant=ctx.tolerant),
    )


def _stage_finalize_result(ctx: _ParseContext) -> None:
    """Stage 7: 设置 is_success 标志。"""
    ctx.result.is_success = len(ctx.result.errors) == 0


def _stage_cleanup(ctx: _ParseContext) -> None:
    """清理：收集诊断、关闭 archive、释放 linker 引用、重置缓存。"""
    # 收集 linker 诊断（PackageIndex 越界、serial_offset/size 异常等）
    if ctx.result.linker and getattr(ctx.result.linker, 'diagnostics', None):
        ctx.result.diagnostics.extend(ctx.result.linker.diagnostics)
    if ctx.archive:
        # 收集 FArchive 诊断记录（截断检测、偏移越界等）
        archive_diagnostics = ctx.archive.get_diagnostics()
        if archive_diagnostics:
            ctx.result.diagnostics = archive_diagnostics + ctx.result.diagnostics
        ctx.archive.close()

    # Task 8: 释放 linker 对 archive 的引用，允许 GC 回收 (#107-6)
    if ctx.result.linker is not None:
        ctx.result.linker._archive = None

    # Task 9: 重置 Kismet 类级别缓存，防止批量解析时无界增长 (#107-7)
    from uasset_read.kismet.archive import FKismetArchive
    FKismetArchive.reset_warned_offsets()

    # Task 10: 重置 BPGC 字节码缓存 (#107-9)
    from uasset_read.kismet.bytecode_extractor import reset_bpgc_cache
    reset_bpgc_cache()

    # Task 11: 清理 ClassHandlerRegistry 缓存 (#108)
    from uasset_read.parsers.class_registry import reset_default_registry_cache
    reset_default_registry_cache()


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
    lightweight_threshold: Optional[int] = None,
) -> None:
    """共享核心解析逻辑 — 编排 7 个 stage 的解析管线。

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
    """
    ctx = _ParseContext(
        path=path, result=result, tolerant=tolerant, provider=provider,
        mappings_path=mappings_path, game=game, include_parent_assets=include_parent_assets,
        asset_roots=asset_roots, extra_linker_setup=extra_linker_setup,
        lightweight_threshold=lightweight_threshold,
    )
    try:
        _stage_open_bundle_and_archive(ctx)
        if ctx.aborted: return

        # summary 在 open 后立即读取（stage 2 的一部分），然后在 stage 3 读取其余表
        ctx.result.summary = _run_required_stage(
            result=ctx.result, archive=ctx.archive, path=ctx.path, tolerant=ctx.tolerant,
            stage="package_summary", field="summary",
            reader=lambda: read_package_summary(ctx.archive),
        )
        if ctx.result.summary is None:
            return

        _stage_build_parse_context(ctx)
        if ctx.aborted: return
        _stage_read_core_tables(ctx)
        if ctx.aborted: return
        _stage_create_and_link_linker(ctx)
        _stage_preload_exports(ctx)
        if ctx.aborted: return
        _stage_run_post_load_and_post_process(ctx)
        _stage_finalize_result(ctx)
    except VersionError as e:
        _record_parse_stage_error(ctx.result, ctx.archive, ctx.path, "version", "legacy_file_version", e)
        ctx.result.errors.append(str(e))
        ctx.result.is_success = False
        if not tolerant: raise
    except ParseError as e:
        _record_parse_stage_error(ctx.result, ctx.archive, ctx.path, "parse", "parse_error", e)
        ctx.result.errors.append(str(e))
        if e.partial_result:
            for key, value in e.partial_result.items():
                if hasattr(ctx.result, key):
                    setattr(ctx.result, key, value)
        ctx.result.is_success = False
        if not tolerant: raise
    except Exception as e:
        _record_parse_stage_error(ctx.result, ctx.archive, ctx.path, "parse", "unexpected", e)
        ctx.result.errors.append(f"Unexpected error: {str(e)}")
        ctx.result.is_success = False
        if not tolerant: raise
    finally:
        _stage_cleanup(ctx)


def parse_package(
    path: str,
    tolerant: bool = True,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    provider: Optional[PackageProvider] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
    lightweight_threshold: Optional[int] = None,
) -> ParseResult:
    """
    主入口：解析 Unreal package（.uasset 或 .umap）。

    Args:
        path: .uasset/.umap 文件路径
        tolerant: 是否启用容错模式（默认开启）
        provider: 可选 package provider（filesystem/pak/iostore）
        mappings_path: 类型映射文件路径
        game: 游戏标识
        lightweight_threshold: 轻量解析阈值

    Returns:
        ParseResult 实例（含解析数据和错误信息）
    """
    result = ParseResult()

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
