from __future__ import annotations

"""Parse stage functions -- core table reads, secondary table reads, export property parsing.

This module contains the stage-level building blocks of the uasset parse lifecycle.
Extracted from ``uasset_read.parse_stages`` as part of the pipeline consolidation
(task #458).
"""

import logging
import struct
from typing import TYPE_CHECKING, Optional, List, Callable

if TYPE_CHECKING:
    from uasset_read.link.linker import PackageLinker
    from uasset_read.package import PackageProvider

from uasset_read.exceptions import ParseError, VersionError
from uasset_read.package import open_package_bundle
from uasset_read.serializers.package_summary import (
    read_package_summary, read_name_table, read_depends_map,
    read_preload_dependencies, validate_export_data_range,
    read_soft_package_references,
)
from uasset_read.versioning import build_version_container
from uasset_read.serializers.object_resources import (
    read_import_map, read_export_map, read_soft_object_paths,
)
from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.parsers.asset_registry_parser import read_asset_registry_data
from uasset_read.constants import PKG_Cooked
from uasset_read.models.diagnostics import OffsetRangeDiagnostic
from uasset_read.models.validators import validate_parse_status

logger = logging.getLogger(__name__)


def _package_metadata(bundle) -> dict:
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
    error_msg = f"{type(error).__name__}: {error}"
    error_key = (type(error).__name__, stage, error_msg)
    if error_key not in result._error_keys:
        result._error_keys.add(error_key)
        result.errors.append(error_msg)
    file_size = 0
    current_pos = 0
    if archive is not None:
        try:
            file_size = archive.total_size()
        except (OSError, OverflowError):
            file_size = getattr(archive, "_file_size", 0) or 0
        try:
            current_pos = archive.tell()
        except (OSError, OverflowError):
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
    except (VersionError, ParseError) as e:
        if not tolerant:
            raise
        _record_parse_stage_error(result, archive, path, stage, field, e)
        return None
    except Exception as e:
        if not tolerant:
            raise
        logger.exception("Unexpected error in parse stage %s: %s", stage, e)
        _record_parse_stage_error(result, archive, path, stage, field, e)
        return None


def _derive_package_name(path: str, summary) -> None:
    """Derive package_name from file path when it is empty."""
    from pathlib import Path
    if summary.package_name:
        return
    _p = Path(path)
    _path_str = _p.as_posix()
    _content_idx = _path_str.lower().find("/content/")
    if _content_idx >= 0:
        _relative = _path_str[_content_idx + len("/content/"):]
        if _relative.startswith("/"):
            _relative = _relative[1:]
        if _relative.lower().endswith(".uasset"):
            _relative = _relative[:-len(".uasset")]
        summary.package_name = f"/Game/{_relative}"
    else:
        summary.package_name = f"/Game/{_p.stem}"


def _init_parse_env(
    path: str,
    result,
    tolerant: bool,
    provider: Optional["PackageProvider"],
    mappings_path: Optional[str],
    game: Optional[str],
    check_aes_key: Optional[bytes],
    hex_view: bool,
    budget=None,
):
    """Initialize parse environment: validate parameters, open archive, read mmap info.

    Returns (archive, bundle, mappings_provider) or None when early-return condition is met.
    """
    if check_aes_key is not None:
        raise ParseError(
            "Unsupported argument: aes_key. Pass the key "
            "when constructing the Pak/IoStore reader and provider"
        )

    mappings_provider = None
    if mappings_path:
        from uasset_read.mappings import TypeMappingsProvider
        mappings_provider = TypeMappingsProvider.from_file(mappings_path, budget=budget)
        result.metadata["mappings_path"] = mappings_path
    if game:
        result.metadata["game"] = game

    bundle = open_package_bundle(path, provider=provider, tolerant=tolerant, budget=budget)
    archive = bundle.open_archive(tolerant=tolerant)
    if hex_view:
        archive.enable_hex_view(True)
    result.metadata.update(_package_metadata(bundle))

    mmap_info = archive.get_mmap_info()
    result.mmap_used = mmap_info["used"]
    result.mmap_warning = mmap_info["warning"]

    return archive, bundle, mappings_provider


def _read_core_tables(
    archive,
    result,
    path: str,
    tolerant: bool,
    memory_monitor=None,
    mappings_provider=None,
    validate_range: bool = True,
    budget=None,
) -> bool:
    """Read summary + name + import + export core tables.

    Returns True on success; early return (when a stage fails) returns False.
    """
    # Read file header
    result.summary = _run_required_stage(
        result=result, archive=archive, path=path, tolerant=tolerant,
        stage="package_summary", field="summary",
        reader=lambda: read_package_summary(archive, budget=budget),
    )
    if result.summary is None:
        return False
    if memory_monitor is not None:
        memory_monitor.checkpoint("package_summary")
    result.version_container = build_version_container(result.summary)
    archive._file_version_ue5 = result.summary.file_version_ue5

    # Mark UE4 legacy assets
    if getattr(result.summary, "is_legacy", False):
        result.metadata["is_legacy"] = True

    # Truncated file detection: validate export data range
    if validate_range:
        try:
            validate_export_data_range(archive, result.summary)
        except (OSError, struct.error, ValueError) as e:
            if not tolerant:
                raise
            _record_parse_stage_error(
                result, archive, path, "package_summary", "export_data_range", e
            )
            return False

    # Read name table
    result.name_map = _run_required_stage(
        result=result, archive=archive, path=path, tolerant=tolerant,
        stage="name_table", field="name_map",
        reader=lambda: read_name_table(archive, result.summary),
    )
    if result.name_map is None:
        result.name_map = []
        return False
    if memory_monitor is not None:
        memory_monitor.checkpoint("name_map")
    _derive_package_name(path, result.summary)

    # Read import table
    result.import_map = _run_required_stage(
        result=result, archive=archive, path=path, tolerant=tolerant,
        stage="import_map", field="import_map",
        reader=lambda: read_import_map(archive, result.summary, result.name_map),
    )
    if result.import_map is None:
        result.import_map = []
        return False
    if memory_monitor is not None:
        memory_monitor.checkpoint("import_map")

    # Read export table
    result.export_map = _run_required_stage(
        result=result, archive=archive, path=path, tolerant=tolerant,
        stage="export_map", field="export_map",
        reader=lambda: read_export_map(archive, result.summary, result.name_map),
    )
    if result.export_map is None:
        result.export_map = []
        return False
    if memory_monitor is not None:
        memory_monitor.checkpoint("export_map")

    return True


def _read_secondary_tables(
    archive,
    result,
    tolerant: bool,
    linker,
    mappings_provider,
    path: str,
    memory_monitor,
    extra_linker_setup=None,
    budget=None,
) -> None:
    """Read DependsMap / SoftPackageReferences / SoftObjectPathList / AssetRegistryData."""
    # Read DependsMap (dependency table) and PreloadDependencies (preload dependencies)
    if hasattr(result.summary, 'depends_offset'):
        result.summary.depends_map = read_depends_map(archive, result.summary, budget=budget)
    if hasattr(result.summary, 'preload_dependency_count'):
        result.summary.preload_dependencies = read_preload_dependencies(archive, result.summary)

    # Read SoftPackageReferences (soft package reference table)
    if hasattr(result.summary, 'soft_package_references_count') and result.summary.soft_package_references_count > 0:
        result.soft_package_references = read_soft_package_references(archive, result.summary, result.name_map)

    # Read SoftObjectPathList (UE5.7+ for indexed SoftObjectProperty parsing)
    if hasattr(result.summary, 'soft_object_paths_count') and result.summary.soft_object_paths_count > 0:
        result.soft_object_path_list = read_soft_object_paths(
            archive, result.summary, result.name_map
        )
    else:
        result.soft_object_path_list = []

    # Store soft_object_path_list on summary for property parser access
    setattr(result.summary, '_soft_object_path_list', result.soft_object_path_list)

    # Read AssetRegistryData (asset metadata tags)
    try:
        is_cooked = bool(result.summary.package_flags & PKG_Cooked)
        result.asset_registry_data = read_asset_registry_data(
            archive,
            result.summary.asset_registry_data_offset,
            file_version_ue4=result.summary.file_version_ue4,
            is_cooked=is_cooked,
        )
    except (struct.error, OSError, ValueError) as e:
        if not tolerant:
            raise ParseError(f"AssetRegistryData parse failed: {e}") from e
        result.warnings.append(f"AssetRegistryData parse failed: {e}")
        result.asset_registry_data = None
    else:
        # Parser succeeded but returned corrupted data -- surface degradation
        if (
            result.asset_registry_data is not None
            and getattr(result.asset_registry_data, "corrupted", False)
        ):
            result.warnings.append(
                "AssetRegistryData is corrupted -- only partial data was recovered"
            )


def _parse_export_properties(
    archive,
    result,
    linker,
    tolerant: bool,
    mappings_provider,
    game: str,
    memory_monitor,
    budget=None,
) -> None:
    """Parse ExportMap properties — unified dispatch via linker.preload()."""
    # Lazy import of extras module (per #117 core/extras layering)
    from uasset_read.blueprint import extract_component_transforms
    from uasset_read.memory_safety import MemoryLimitExceeded

    _mappings = mappings_provider.mappings if mappings_provider else None
    for _exp_idx, export in enumerate(result.export_map or []):
        memory_monitor.checkpoint(f"export[{_exp_idx}]")

        if export.serial_size > 0:
            try:
                if linker is not None:
                    linker.preload(
                        _exp_idx,
                        mappings=_mappings,
                        game=game,
                        tolerant=tolerant,
                    )
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
                    setattr(export, "parse_status", validate_parse_status("success"))
                elif getattr(export, "parse_status", None) in ("opaque", "partial_metadata"):
                    pass
            except MemoryLimitExceeded:
                raise
            except MemoryError as e:
                logger.error(
                    "MemoryError parsing export %s: %s",
                    getattr(export, "object_name", "?"), e
                )
                export.properties = []
                setattr(export, "parse_status", validate_parse_status("partial"))
                setattr(export, "fallback_reason", "memory_error_partial")
                setattr(export, "error_message", str(e))
                if not tolerant:
                    raise
            except (struct.error, OSError, ValueError, KeyError, AttributeError) as e:
                if not tolerant:
                    raise ParseError(f"Property parse error in {export.object_name}: {e}") from e
                result.errors.append(f"Property parse error in {export.object_name}: {e}")
                export.properties = []
                setattr(export, "parse_status", validate_parse_status("failed"))
                setattr(export, "fallback_reason", "parse_error")
                setattr(export, "error_message", str(e))

            # Extract component transform properties
            if export.properties:
                export.transforms = extract_component_transforms(export.properties)


def _create_linker(
    archive,
    summary,
    name_map: List[str],
    import_map,
    export_map,
    result,
    tolerant: bool = True,
    version_container=None,
    extra_linker_setup: Optional[Callable] = None,
) -> Optional["PackageLinker"]:
    """Create and link PackageLinker. Returns linker or None."""
    from uasset_read.link.linker import PackageLinker
    try:
        linker = PackageLinker(
            archive, summary, name_map,
            import_map, export_map or [],
            version_container=version_container,
        )
        linker.link()
        result.linker = linker
        if extra_linker_setup is not None:
            extra_linker_setup(linker, result)
        return linker
    except (OSError, struct.error, ValueError, AttributeError, KeyError) as e:
        if not tolerant:
            raise ParseError(f"Linker creation failed: {e}") from e
        result.errors.append(f"Linker creation failed: {e}")
        return None


def _read_package_headers(
    path: str,
    result,
    tolerant: bool = True,
    provider: Optional["PackageProvider"] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
    hex_view: bool = False,
    validate_range: bool = True,
    check_aes_key: Optional[bytes] = None,
) -> tuple:
    """Read package file header (Summary + NameTable + ImportMap + ExportMap + Linker).

    Reuses _init_parse_env + _read_core_tables, additionally creates linker.

    Returns:
        (bundle, archive, linker, mappings_provider) — caller is responsible for closing archive.
        If result.summary is None, it indicates early failure; caller should return directly.
    """
    # Initialize parse environment (archive, bundle, mappings_provider)
    archive, bundle, mappings_provider = _init_parse_env(
        path, result, tolerant, provider, mappings_path, game,
        check_aes_key=check_aes_key, hex_view=hex_view,
    )

    # Read core tables (summary/name/import/export)
    if not _read_core_tables(
        archive, result, path, tolerant,
        validate_range=validate_range,
    ):
        return bundle, archive, None, mappings_provider

    # Create linker
    linker = _create_linker(
        archive, result.summary, result.name_map,
        result.import_map, result.export_map or [],
        result, tolerant=tolerant,
        version_container=result.version_container,
    )

    return bundle, archive, linker, mappings_provider
