"""主解析管线入口 — parse_uasset() 函数。

等价迁移 uasset_read.py §6223-6412。
"""
from __future__ import annotations

import logging
import struct
import warnings
from typing import TYPE_CHECKING, Sequence, Callable
from pathlib import Path

if TYPE_CHECKING:
    from uasset_read.memory_safety import MemoryPolicy
    from uasset_read.link.result import LinkerParseResult
    from uasset_read.config import ParseConfig

from uasset_read.memory_safety import MemoryLimitExceeded
from uasset_read.constants import (
    LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD,
    CONTROL_RIG_LARGE_FILE_THRESHOLD,
    CONTROL_RIG_LARGE_FILE_CLASSES,
)
from uasset_read.archive import FArchive
from uasset_read.exceptions import VersionError, ParseError
from uasset_read.package import PackageProvider
from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.models.result import ParseResult
from uasset_read.project_logging import configure_project_logging
from uasset_read.parse_stages import (
    _record_parse_stage_error,
    _init_parse_env,
    _read_core_tables,
    _read_secondary_tables,
    _parse_export_properties,
    _create_linker,
    _read_package_headers,
)
from uasset_read.parse_post_process import _post_process

logger = logging.getLogger(__name__)


def _should_use_lightweight_tolerant_parse(
    result,
    tolerant: bool,
    lightweight_threshold: int | None = None,
    force_full_parse: bool = False,
) -> bool:
    if force_full_parse:
        return False
    if not tolerant or result.summary is None:
        return False
    threshold = (
        lightweight_threshold
        if lightweight_threshold is not None
        else LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD
    )
    # ControlRig 等大型文件：检测 export 类名，使用更高的阈值
    if (
        threshold == LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD
        and lightweight_threshold is None
        and _is_large_file_asset(result)
    ):
        threshold = CONTROL_RIG_LARGE_FILE_THRESHOLD
    return getattr(result.summary, "export_count", 0) > threshold


def _is_large_file_asset(result) -> bool:
    """检测是否为 ControlRig/RigVM 等天然大型文件资产。

    通过 export 类名子串匹配判断，避免将这类资产误判为超大蓝图。
    参考: UE ControlRig.cpp 序列化结构。
    """
    from uasset_read.serializers.object_resources import resolve_class_name
    export_map = getattr(result, "export_map", None) or []
    import_map = getattr(result, "import_map", None) or []
    # 仅检查前 20 个 export 的类名即可判断（避免全量扫描性能开销）
    for export in export_map[:20]:
        try:
            class_name = resolve_class_name(
                export.class_index, import_map, export_map
            )
        except (AttributeError, TypeError, IndexError):
            continue
        if class_name and any(sub in class_name for sub in CONTROL_RIG_LARGE_FILE_CLASSES):
            return True
    return False


def _build_lightweight_graphs(result) -> list:
    """在轻量模式下提取基本图信息（仅名称）。"""
    from uasset_read.serializers.object_resources import get_asset_class
    from uasset_read.models.core import UEdGraph

    graphs = []
    if not result.export_map or not result.import_map:
        return graphs

    for export in result.export_map:
        name = str(getattr(export, "object_name", "") or "")
        if not name:
            continue

        # 检测 EdGraph 类型导出
        class_name = get_asset_class(export, result.import_map, result.export_map)
        if class_name in ("EdGraph", "UberEdGraph"):
            # 创建最小化的 UEdGraph，仅包含名称
            graph = UEdGraph(
                graph_name=name,
                graph_class=class_name,
                nodes=[],
            )
            graphs.append(graph)

    return graphs


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


def _apply_lightweight_parse(
    result,
    tolerant: bool,
    lightweight_threshold: int | None,
    force_full_parse: bool,
) -> bool:
    """轻量解析路径：若触发则填充 result 并返回 True。"""
    if not _should_use_lightweight_tolerant_parse(result, tolerant, lightweight_threshold, force_full_parse):
        return False
    result.warnings.append(
        "Lightweight tolerant parse used due to export complexity "
        f"(exports={getattr(result.summary, 'export_count', 0)})"
    )
    result.metadata["lightweight_tolerant_parse"] = True
    result.metadata["function_graphs_fallback"] = _build_lightweight_function_graphs(result.export_map)
    result.graphs = _build_lightweight_graphs(result)
    if result.graphs and result.export_map:
        for export in result.export_map:
            name = str(getattr(export, "object_name", "") or "")
            if name.endswith("_C") and not name.startswith("Default__"):
                export.graphs = result.graphs
                break
    result.is_success = not result.errors
    return True


def _run_linker_post_load(linker, result, tolerant: bool) -> None:
    """执行 linker.post_load() 并处理异常。"""
    if linker is None:
        return
    try:
        linker.post_load()
    except (OSError, struct.error, ValueError, AttributeError) as e:
        if not tolerant:
            raise ParseError(f"Linker post_load failed: {e}") from e
        result.errors.append(f"Linker post_load failed: {e}")
    # Propagate import verification errors from linker to result
    if hasattr(linker, '_import_verification_errors') and linker._import_verification_errors:
        result.errors.extend(linker._import_verification_errors)


def _handle_parse_error(
    exc: Exception,
    result,
    archive,
    path: str,
    tolerant: bool,
) -> None:
    """统一处理解析异常（VersionError / ParseError / MemoryError / 其他）。

    注意：错误记录统一通过 _record_parse_stage_error 完成（含去重），
    不再额外调用 result.errors.append，避免重复记录。
    """

    if isinstance(exc, MemoryLimitExceeded):
        raise

    if isinstance(exc, VersionError):
        _record_parse_stage_error(result, archive, path, "version", "legacy_file_version", exc)
        result.is_success = False
    elif isinstance(exc, ParseError):
        _record_parse_stage_error(result, archive, path, "parse", "parse_error", exc)
        if exc.partial_result:
            for key, value in exc.partial_result.items():
                if hasattr(result, key):
                    setattr(result, key, value)
        result.is_success = False
    elif isinstance(exc, MemoryError):
        error_msg = f"MemoryError: {exc}"
        if error_msg not in result.errors:
            result.errors.append(error_msg)
        result.is_success = False
    else:
        _record_parse_stage_error(result, archive, path, "parse", "unexpected", exc)
        result.is_success = False

    if not tolerant:
        raise


def _cleanup_archive_diagnostics(result, archive) -> None:
    """收集 linker/FArchive 诊断记录并在最后关闭 archive。"""
    if result.linker and getattr(result.linker, 'diagnostics', None):
        result.diagnostics.extend(result.linker.diagnostics)
    if archive:
        archive_diagnostics = archive.get_diagnostics()
        if archive_diagnostics:
            result.diagnostics = archive_diagnostics + result.diagnostics
        if archive.is_hex_view_enabled():
            result.hex_view_entries = archive.get_hex_view_entries()
        archive.close()


def _cleanup_parse_memory(result) -> None:
    """统一内存清理 — 打破循环引用、重置全局缓存。

    在 parse_package / parse_package_lazy 的 finally 块中调用，
    防止批量解析时 UObjectInstance ↔ linker 循环引用导致的内存泄漏，
    以及全局缓存（ClassHandlerRegistry）无界增长。
    """
    # 打破 UObjectInstance ↔ linker 循环引用
    if result is not None and result.linker is not None:
        try:
            for obj in result.linker._export_objects:
                obj.linker = None
            for obj in result.linker._import_objects:
                obj.linker = None
            result.linker._export_objects.clear()
            result.linker._import_objects.clear()
            result.linker._root_objects.clear()
            result.linker._preload_cache.clear()
            result.linker._archive = None
        except Exception:
            pass
    # 清理全局缓存，防止无界增长
    try:
        from uasset_read.parsers.class_registry import get_class_registry
        get_class_registry().reset_cache()
    except Exception:
        pass


def _parse_package_core(
    path: str,
    result,
    tolerant: bool | None = None,
    provider: PackageProvider | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    include_parent_assets: bool | None = None,
    asset_roots: Sequence[str] | None = None,
    extra_linker_setup: Callable | None = None,
    check_aes_key: bytes | None = None,
    lightweight_threshold: int | None = None,
    force_full_parse: bool | None = None,
    hex_view: bool | None = None,
    memory_policy: MemoryPolicy | None = None,
) -> None:
    """共享核心解析逻辑 — 读取 package 并填充 result。

    Args:
        path: 文件路径
        result: ParseResult 或 LinkerParseResult 实例（被原地修改）
        tolerant: 容错模式（None 表示使用默认 True）
        provider: package provider
        mappings_path: 类型映射文件路径
        game: 游戏标识
        include_parent_assets: 是否解析父资产（None 表示使用默认 False）
        asset_roots: 资产根目录列表
        extra_linker_setup: linker 创建后的额外回调 (linker, result) -> None
        check_aes_key: 如果提供则抛出 ParseError（parse_package 兼容）
        force_full_parse: 强制完整解析大蓝图（None 表示使用默认 False）
        hex_view: 启用 HexView 字节偏移追踪（None 表示使用默认 False）
    """
    # 将 None 解析为内部默认值
    if tolerant is None:
        tolerant = True
    if include_parent_assets is None:
        include_parent_assets = False
    if force_full_parse is None:
        force_full_parse = False
    if hex_view is None:
        hex_view = False

    from uasset_read.memory_safety import (
        MemoryMonitor,
        MemoryPolicy,
    )

    archive = None
    bundle = None

    file_path = Path(path)
    file_size = file_path.stat().st_size if file_path.is_file() else 0
    policy = memory_policy or MemoryPolicy()
    memory_monitor = MemoryMonitor(
        asset_path=path,
        limits=policy.limits_for_size(file_size),
    )

    with memory_monitor:
        try:
            # 初始化环境
            init_result = _init_parse_env(
                path, result, tolerant, provider, mappings_path, game,
                check_aes_key, hex_view,
            )
            if init_result is None:
                return
            archive, bundle, mappings_provider = init_result

            # 读取核心表（summary/name/import/export）
            if not _read_core_tables(
                archive, result, path, tolerant, memory_monitor, mappings_provider,
            ):
                return

            # 读取 secondary 表 + 创建 linker
            _read_secondary_tables(
                archive, result, tolerant, linker=None,
                mappings_provider=mappings_provider,
                path=path, memory_monitor=memory_monitor,
            )
            linker = _create_linker(
                archive, result.summary, result.name_map,
                result.import_map, result.export_map or [],
                result, tolerant=tolerant,
                version_container=result.version_container,
                extra_linker_setup=extra_linker_setup,
            )

            # 轻量解析路径（提前返回）
            if _apply_lightweight_parse(result, tolerant, lightweight_threshold, force_full_parse):
                return

            # 完整解析：preload → post_load → post_process
            _parse_export_properties(
                archive, result, linker, tolerant, mappings_provider, game, memory_monitor,
            )
            memory_monitor.checkpoint("post_load")
            _run_linker_post_load(linker, result, tolerant)
            memory_monitor.checkpoint("post_process")

            _post_process(
                path, archive, result.summary, result.name_map,
                result.import_map, result.export_map or [], result, tolerant,
                linker=linker,
                include_parent_assets=include_parent_assets,
                asset_roots=asset_roots,
                archive_factory=lambda: bundle.open_archive(tolerant=tolerant) if bundle else FArchive(path, tolerant=tolerant),
                memory_policy=policy,
            )

            # 将 result.graphs 分配给蓝图 export（IR 构建器从 export.graphs 读取）
            if result.graphs and result.export_map:
                for export in result.export_map:
                    name = str(getattr(export, "object_name", "") or "")
                    if name.endswith("_C") and not name.startswith("Default__"):
                        export.graphs = result.graphs
                        break  # 只分配给主蓝图 export

            result.is_success = not result.errors

        except Exception as e:
            _handle_parse_error(e, result, archive, path, tolerant)

        finally:
            _cleanup_archive_diagnostics(result, archive)


def _resolve_parse_params(
    config: ParseConfig | None,
    kwargs: dict,
) -> dict:
    """将 ParseConfig 和旧风格关键字参数合并为最终参数字典。

    - 若提供 config，config 的值作为默认，显式传入的旧参数可覆盖。
    - 若未提供 config，旧参数保持原样。
    - 对同时从 config 和旧参数传入的值，发出 DeprecationWarning。

    kwargs 中值为 None 的条目视为"调用方未指定"，不覆盖 config 值。
    """
    if config is None:
        return kwargs

    # 所有旧参数在 parse_package() 签名中默认为 None（哨兵），
    # 只有调用方显式传入非 None 值才算"显式覆盖"。
    # 但如果调用方显式传入了与 config 值不同的非 None 值，发出弃用警告。
    conflicting = []
    for fld in config.__dataclass_fields__:
        if fld in kwargs and kwargs[fld] is not None:
            config_val = getattr(config, fld)
            if config_val is not None and kwargs[fld] != config_val:
                conflicting.append(fld)

    if conflicting:
        warnings.warn(
            f"同时传入 config 和旧参数 {conflicting}，旧参数将覆盖 config 中的对应值。"
            "请统一使用 ParseConfig。",
            DeprecationWarning,
            stacklevel=3,
        )

    # 合并：kwargs 非 None 值覆盖 config，None 不覆盖
    merged = {}
    for fld in config.__dataclass_fields__:
        kw_val = kwargs.get(fld)
        merged[fld] = kw_val if kw_val is not None else getattr(config, fld)
    # 保留 kwargs 中不在 config 中的键（如 path, provider 等）
    for key in kwargs:
        if key not in merged:
            merged[key] = kwargs[key]
    return merged


def parse_package(
    path: str,
    tolerant: bool | None = None,
    include_parent_assets: bool | None = None,
    asset_roots: Sequence[str] | None = None,
    aes_key: bytes | None = None,
    provider: PackageProvider | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    include_linker: bool = True,  # 已废弃，linker 始终创建
    lightweight_threshold: int | None = None,
    force_full_parse: bool | None = None,
    hex_view: bool | None = None,
    memory_policy: MemoryPolicy | None = None,
    config: ParseConfig | None = None,
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
        force_full_parse: 强制完整解析大蓝图（忽略轻量模式阈值）
        hex_view: 启用 HexView 字节偏移追踪
        config: 可选 ParseConfig 实例，集中管理解析参数。
            传入 config 时，旧风格的个别参数仍可覆盖 config 中的值
            （但不推荐混用）。

    Returns:
        ParseResult 实例（含解析数据和错误信息）
    """
    result = ParseResult()

    # 处理已废弃的 include_linker 参数
    if include_linker is not True:
        warnings.warn(
            "include_linker 参数已废弃，linker 始终包含在结果中。"
            "请移除该参数调用。",
            DeprecationWarning,
            stacklevel=2,
        )

    # Handle deprecated aes_key inline (don't pass to core)
    if aes_key is not None:
        result.errors.append(
            "Unsupported argument: aes_key. Pass the key "
            "when constructing the Pak/IoStore reader and provider"
        )
        result.is_success = False
        return result

    # 合并 config 和旧参数
    core_kwargs = _resolve_parse_params(config, {
        "tolerant": tolerant,
        "include_parent_assets": include_parent_assets,
        "asset_roots": asset_roots,
        "mappings_path": mappings_path,
        "game": game,
        "force_full_parse": force_full_parse,
        "hex_view": hex_view,
        "lightweight_threshold": lightweight_threshold,
        "memory_policy": memory_policy,
    })

    _parse_package_core(
        path, result,
        provider=provider,
        **core_kwargs,
    )
    _cleanup_parse_memory(result)
    return result


def parse_uasset(
    path: str,
    tolerant: bool | None = None,
    include_parent_assets: bool | None = None,
    asset_roots: Sequence[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    include_linker: bool = True,  # 已废弃，linker 始终创建
    force_full_parse: bool | None = None,
    memory_policy: MemoryPolicy | None = None,
    config: ParseConfig | None = None,
) -> ParseResult:
    """
    兼容入口：解析 .uasset 文件。

    Internally delegates to parse_package(), so sidecar payload discovery is
    shared with .umap/package parsing.
    """
    # 处理已废弃的 include_linker 参数
    if include_linker is not True:
        warnings.warn(
            "include_linker 参数已废弃，linker 始终包含在结果中。"
            "请移除该参数调用。",
            DeprecationWarning,
            stacklevel=2,
        )

    return parse_package(
        path,
        tolerant=tolerant,
        include_parent_assets=include_parent_assets,
        asset_roots=asset_roots,
        mappings_path=mappings_path,
        game=game,
        force_full_parse=force_full_parse,
        memory_policy=memory_policy,
        config=config,
    )


def parse_uasset_with_linker(
    path: str,
    tolerant: bool | None = None,
    preload_all: bool = False,
    include_parent_assets: bool | None = None,
    asset_roots: Sequence[str] | None = None,
    provider: PackageProvider | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    lightweight_threshold: int | None = None,
    force_full_parse: bool | None = None,
    hex_view: bool | None = None,
    memory_policy: MemoryPolicy | None = None,
    config: ParseConfig | None = None,
) -> "LinkerParseResult":
    """使用 PackageLinker 的并行解析入口（D-01, D-04）。

    Args:
        path: .uasset 文件路径
        tolerant: 是否启用容错模式（默认开启）
        preload_all: 是否预加载所有 exports（默认 False，惰性加载）
        provider: 可选 package provider（filesystem/pak/iostore）
        force_full_parse: 强制完整解析大蓝图（忽略轻量模式阈值）
        hex_view: 启用 HexView 字节偏移追踪
        config: 可选 ParseConfig 实例，集中管理解析参数。

    Returns:
        LinkerParseResult 实例（含对象图和后处理数据）
    """
    # 延迟导入 extras 模块（per #117 core/extras 分层）
    from uasset_read.link.result import LinkerParseResult

    result = LinkerParseResult()

    def extra_linker_setup(linker, res):
        res.all_objects = linker._import_objects + linker._export_objects
        res.root_objects = linker._root_objects

    # 合并 config 和旧参数
    core_kwargs = _resolve_parse_params(config, {
        "tolerant": tolerant,
        "include_parent_assets": include_parent_assets,
        "asset_roots": asset_roots,
        "mappings_path": mappings_path,
        "game": game,
        "force_full_parse": force_full_parse,
        "hex_view": hex_view,
        "lightweight_threshold": lightweight_threshold,
        "memory_policy": memory_policy,
    })

    _parse_package_core(
        path, result,
        provider=provider,
        extra_linker_setup=extra_linker_setup,
        **core_kwargs,
    )

    if preload_all and result.linker:
        for i in range(len(result.linker._export_objects)):
            try:
                result.linker.preload(i)
            except ParseError as e:
                logger.warning("预加载 export %d 失败，跳过: %s", i, e)
            except Exception as e:
                logger.exception("预加载 export %d 意外错误: %s", i, e)

    return result


def parse_package_lazy(
    path: str,
    export_indices: list[int] | None = None,
    store_raw_bytes: bool = False,
    tolerant: bool = True,
    provider: PackageProvider | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    memory_policy: MemoryPolicy | None = None,
) -> ParseResult:
    """懒加载模式解析包 — 按需解析 export body。

    始终解析：Header、NameMap、ImportMap、ExportMap（元数据）。
    仅解析指定 export_indices 的 body；未指定时所有 export 标记为未加载。

    当 provider 提供 open_file() 时，优先使用它获取 archive（支持 mmap
    范围读取），避免将整个文件读入内存；否则回退到 read_file() 路径。

    Args:
        path: .uasset/.umap 文件路径
        export_indices: 需要解析 body 的 export 索引列表，None 表示全部跳过
        store_raw_bytes: 是否将 export body 原始字节存入 lazy_load_archive
            （默认 False — 懒加载场景不缓存原始字节以节省内存）
        tolerant: 容错模式
        provider: 可选 package provider
        mappings_path: 类型映射文件路径
        game: 游戏标识
        memory_policy: 内存策略

    Returns:
        ParseResult 实例（export body 按需解析）
    """
    from uasset_read.blueprint import extract_component_transforms

    result = ParseResult()
    archive = None
    linker = None

    # 当 provider 提供 open_file() 时，直接用它获取 archive，
    # 避免通过 open_package_bundle() 将整个文件读入内存。
    # open_file() 支持 mmap 范围读取，适合懒加载场景。
    use_direct_archive = (
        provider is not None
        and hasattr(provider, 'open_file')
        and callable(getattr(provider, 'open_file', None))
    )

    try:
        mappings_provider = None
        if mappings_path:
            from uasset_read.mappings import TypeMappingsProvider
            mappings_provider = TypeMappingsProvider.from_file(mappings_path)
            result.metadata["mappings_path"] = mappings_path
        if game:
            result.metadata["game"] = game

        if use_direct_archive:
            # 快速路径：通过 open_file() 获取 archive，不读取整个文件
            archive = provider.open_file(path)
            if archive is None:
                raise FileNotFoundError(f"Package not found: {path}")

            # 读取核心表
            if not _read_core_tables(
                archive, result, path, tolerant,
                validate_range=True,
            ):
                if result.summary is None:
                    return result

            # 读取 secondary 表
            _read_secondary_tables(
                archive, result, tolerant, linker=None,
                mappings_provider=mappings_provider,
                path=path, memory_monitor=None,
            )
        else:
            # 回退路径：通过 bundle 读取（read_file）
            bundle_obj, archive, linker, mappings_provider = _read_package_headers(
                path, result,
                tolerant=tolerant, provider=provider,
                mappings_path=mappings_path, game=game,
            )
            if result.summary is None:
                return result

        # 按需解析指定 export body
        parse_indices = set(export_indices) if export_indices else set()
        _mappings = mappings_provider.mappings if mappings_provider else None

        for idx, export in enumerate(result.export_map or []):
            if idx in parse_indices and export.serial_size > 0:
                try:
                    if linker is not None:
                        linker.preload(
                            idx, mappings=_mappings, game=game, tolerant=tolerant,
                        )
                        inst = linker._export_objects[idx]
                        export.properties = inst.serialized_properties
                    else:
                        export.properties = parse_properties_from_export(
                            export, archive, result.summary, result.name_map,
                            result.export_map or [], result.import_map,
                            linker=linker, mappings=_mappings, game=game,
                            tolerant=tolerant,
                        )
                    if not getattr(export, "parse_status", None):
                        setattr(export, "parse_status", "success")
                    elif getattr(export, "parse_status", None) in ("opaque", "partial_metadata"):
                        pass
                except (struct.error, OSError, ValueError, KeyError, AttributeError) as e:
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

            # 存储原始字节（可选）
            if store_raw_bytes and export.serial_size > 0:
                try:
                    archive.seek(export.serial_offset)
                    setattr(export, "lazy_load_archive", archive.read_bytes(export.serial_size))
                except (OSError, struct.error) as e:
                    if not tolerant:
                        raise ParseError(
                            f"读取 export {export.object_name} 原始字节失败: {e}"
                        ) from e
                    setattr(export, "lazy_load_archive", None)

            # 设置懒加载标记（通过 setattr 兼容 ObjectExport 和 ExportIR）
            setattr(export, "is_loaded", idx in parse_indices)

        # post_load
        if linker is not None:
            try:
                linker.post_load()
            except (OSError, struct.error, ValueError, AttributeError) as e:
                if not tolerant:
                    raise ParseError(f"Linker post_load failed: {e}") from e
                result.errors.append(f"Linker post_load failed: {e}")
            # Propagate import verification errors from linker to result
            if hasattr(linker, '_import_verification_errors') and linker._import_verification_errors:
                result.errors.extend(linker._import_verification_errors)

        result.is_success = not result.errors
        result.metadata["lazy_loading"] = True
        result.metadata["loaded_exports"] = sorted(parse_indices)
        result.metadata["total_exports"] = len(result.export_map or [])

    except VersionError as e:
        _record_parse_stage_error(result, archive, path, "version", "legacy_file_version", e)
        result.is_success = False
        if not tolerant:
            raise
    except ParseError as e:
        _record_parse_stage_error(result, archive, path, "parse", "parse_error", e)
        result.is_success = False
        if not tolerant:
            raise
    except Exception as e:
        _record_parse_stage_error(result, archive, path, "parse", "unexpected", e)
        result.is_success = False
        if not tolerant:
            raise
    finally:
        if archive:
            archive.close()
        _cleanup_parse_memory(result)

    return result
