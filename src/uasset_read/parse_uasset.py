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
from uasset_read.config import LogConfig
from uasset_read.project_logging import scoped_project_logging, configure_project_logging, current_log_run_id
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
from uasset_read.parse_utils import (
    _should_use_lightweight_tolerant_parse,
    _is_large_file_asset,
    _build_lightweight_graphs,
    _build_lightweight_function_graphs,
    _apply_lightweight_parse,
    _resolve_parse_params,
)
from uasset_read.parse_error_handler import _handle_parse_error
from uasset_read.parse_memory import _cleanup_parse_memory

logger = logging.getLogger(__name__)


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
        ResourceBudget,
        AllocationLimits,
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
    resource_budget = ResourceBudget()

    with memory_monitor:
        try:
            # 初始化环境
            init_result = _init_parse_env(
                path, result, tolerant, provider, mappings_path, game,
                check_aes_key, hex_view, budget=resource_budget,
            )
            if init_result is None:
                return
            archive, bundle, mappings_provider = init_result

            # 读取核心表（summary/name/import/export）
            if not _read_core_tables(
                archive, result, path, tolerant, memory_monitor, mappings_provider,
                budget=resource_budget,
            ):
                return

            # 读取 secondary 表 + 创建 linker
            _read_secondary_tables(
                archive, result, tolerant, linker=None,
                mappings_provider=mappings_provider,
                path=path, memory_monitor=memory_monitor,
                budget=resource_budget,
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


@scoped_project_logging
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
    log_config: LogConfig | None = None,
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
    # #448: Don't reconfigure logging when already inside a scoped session
    # (e.g. called from parse_single/parse_batch with an active log_config).
    already_configured = log_config is None and current_log_run_id() is not None
    if not already_configured:
        configure_project_logging()
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


@scoped_project_logging
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
    log_config: LogConfig | None = None,
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

    # #448: Don't reconfigure logging when already inside a scoped session
    # (e.g. called from parse_single/parse_batch with an active log_config).
    already_configured = log_config is None and current_log_run_id() is not None
    if not already_configured:
        configure_project_logging()

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
    """Lazy-parse mode — parse export bodies on demand.

    Always parses: Header, NameMap, ImportMap, ExportMap (metadata).
    Only parses body for specified export_indices; unspecified exports
    are marked as not loaded.

    When provider offers open_file(), the archive is obtained directly
    (supporting mmap range reads) instead of reading the whole file.

    Error and status semantics are aligned with ``_parse_package_core``:
    - ``MemoryMonitor`` is created from *memory_policy* for RSS checking
    - ``MemoryError`` during export parsing sets status to ``"partial"``
    - ``MemoryLimitExceeded`` is re-raised (never swallowed)
    - All ``parse_status`` values are validated via ``validate_parse_status()``
    - Top-level exceptions use ``_handle_parse_error()``

    Args:
        path: .uasset/.umap file path
        export_indices: export indices whose bodies should be parsed;
            None means skip all bodies
        store_raw_bytes: whether to store raw export bytes in
            lazy_load_archive (default False to save memory)
        tolerant: tolerant mode
        provider: optional package provider
        mappings_path: type mappings file path
        game: game identifier
        memory_policy: memory policy controlling RSS limits

    Returns:
        ParseResult instance (export bodies parsed on demand)
    """
    from uasset_read.blueprint import extract_component_transforms
    from uasset_read.memory_safety import (
        MemoryMonitor,
        MemoryPolicy as _MemoryPolicy,
        ResourceBudget,
    )
    from uasset_read.models.validators import validate_parse_status

    result = ParseResult()
    archive = None
    linker = None

    # When provider offers open_file(), obtain archive directly
    # (supports mmap range reads) instead of reading the whole file.
    use_direct_archive = (
        provider is not None
        and hasattr(provider, 'open_file')
        and callable(getattr(provider, 'open_file', None))
    )

    resource_budget = ResourceBudget()

    # Create MemoryMonitor from memory_policy (aligned with _parse_package_core)
    policy = memory_policy or _MemoryPolicy()
    try:
        file_size = Path(path).stat().st_size if Path(path).is_file() else 0
    except OSError:
        file_size = 0
    memory_monitor = MemoryMonitor(
        asset_path=path,
        limits=policy.limits_for_size(file_size),
    )

    with memory_monitor:
        try:
            mappings_provider = None
            if mappings_path:
                from uasset_read.mappings import TypeMappingsProvider
                mappings_provider = TypeMappingsProvider.from_file(
                    mappings_path, budget=resource_budget,
                )
                result.metadata["mappings_path"] = mappings_path
            if game:
                result.metadata["game"] = game

            if use_direct_archive:
                # Fast path: obtain archive via open_file(), no full-file read
                archive = provider.open_file(path)
                if archive is None:
                    raise FileNotFoundError(f"Package not found: {path}")

                # Read core tables (with memory_monitor checkpoints)
                if not _read_core_tables(
                    archive, result, path, tolerant,
                    memory_monitor=memory_monitor,
                    validate_range=True, budget=resource_budget,
                ):
                    if result.summary is None:
                        return result

                # Read secondary tables (with memory_monitor)
                _read_secondary_tables(
                    archive, result, tolerant, linker=None,
                    mappings_provider=mappings_provider,
                    path=path, memory_monitor=memory_monitor,
                    budget=resource_budget,
                )
            else:
                # Fallback path: read via bundle (read_file)
                bundle_obj, archive, linker, mappings_provider = _read_package_headers(
                    path, result,
                    tolerant=tolerant, provider=provider,
                    mappings_path=mappings_path, game=game,
                    budget=resource_budget,
                )
                if result.summary is None:
                    return result

            # Parse specified export bodies on demand
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
                            setattr(export, "parse_status", validate_parse_status("success"))
                        elif getattr(export, "parse_status", None) in ("opaque", "partial_metadata"):
                            pass
                    except MemoryLimitExceeded:
                        raise
                    except MemoryError as e:
                        logger.error(
                            "MemoryError parsing export %s: %s",
                            getattr(export, "object_name", "?"), e,
                        )
                        export.properties = []
                        setattr(export, "parse_status", validate_parse_status("partial"))
                        setattr(export, "fallback_reason", "memory_error_partial")
                        setattr(export, "error_message", str(e))
                        if not tolerant:
                            raise
                    except (struct.error, OSError, ValueError, KeyError, AttributeError) as e:
                        if not tolerant:
                            raise ParseError(
                                f"Property parse error in {export.object_name}: {e}"
                            ) from e
                        result.errors.append(
                            f"Property parse error in {export.object_name}: {e}"
                        )
                        export.properties = []
                        setattr(export, "parse_status", validate_parse_status("failed"))
                        setattr(export, "fallback_reason", "parse_error")
                        setattr(export, "error_message", str(e))

                    # Extract component transform properties
                    if export.properties:
                        export.transforms = extract_component_transforms(export.properties)

                # Store raw bytes (optional)
                if store_raw_bytes and export.serial_size > 0:
                    try:
                        archive.seek(export.serial_offset)
                        setattr(export, "lazy_load_archive", archive.read_bytes(export.serial_size))
                    except (OSError, struct.error) as e:
                        if not tolerant:
                            raise ParseError(
                                f"Failed to read raw bytes for export {export.object_name}: {e}"
                            ) from e
                        setattr(export, "lazy_load_archive", None)

                # Set lazy-load flag (via setattr for ObjectExport and ExportIR compat)
                setattr(export, "is_loaded", idx in parse_indices)

            # post_load
            if linker is not None:
                _run_linker_post_load(linker, result, tolerant)

            result.is_success = not result.errors
            result.metadata["lazy_loading"] = True
            result.metadata["loaded_exports"] = sorted(parse_indices)
            result.metadata["total_exports"] = len(result.export_map or [])

        except Exception as e:
            _handle_parse_error(e, result, archive, path, tolerant)
        finally:
            _cleanup_archive_diagnostics(result, archive)
            _cleanup_parse_memory(result)

    return result
