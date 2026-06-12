"""Parse pipeline helper functions."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, List, Sequence

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.link.linker import PackageLinker
    from uasset_read.kismet.result import KismetDecompiledResult
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectImport, ObjectExport

from uasset_read.models.diagnostics import OffsetRangeDiagnostic
import logging

logger = logging.getLogger(__name__)


def _is_relative_to(path: Path, root: Path) -> bool:
    """Check if path is relative to root."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _extract_kismet_decompiled(
    path: str,
    archive: "FArchive",
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
            obj_name = export.object_name
            if obj_name.startswith("K2Node_FunctionEntry"):
                class_name = "K2Node_FunctionEntry"
            elif obj_name.startswith("K2Node_FunctionResult"):
                class_name = "K2Node_FunctionResult"
            else:
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
    archive: "FArchive",
    summary: "PackageFileSummary",
    name_map: List[str],
    import_map: List["ObjectImport"],
    export_map: List["ObjectExport"],
    result: Any,
    tolerant: bool = True,
    linker: Optional["PackageLinker"] = None,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    archive_factory: Any = None,
) -> None:
    """Shared post-processing: execute 7 stages via PostProcessPipeline.

    Write to fields via hasattr guard, supports both ParseResult and LinkerParseResult.
    """
    from uasset_read.post_process import PostProcessContext, build_default_pipeline

    ctx = PostProcessContext(
        path=path,
        archive=archive,
        summary=summary,
        name_map=name_map,
        import_map=import_map,
        export_map=export_map,
        result=result,
        tolerant=tolerant,
        linker=linker,
        include_parent_assets=include_parent_assets,
        asset_roots=asset_roots,
        archive_factory=archive_factory,
    )
    pipeline = build_default_pipeline()
    pipeline.execute(ctx)


def _resolve_parent_assets(
    path: str,
    result: Any,
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
        from uasset_read.parse_uasset import parse_uasset_with_linker
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
    """Find parent asset file.

    Security check: reject parent_class containing path traversal characters.
    """
    # Security validation: reject path traversal characters to prevent unauthorized access
    if ".." in parent_class or "/" in parent_class or "\\" in parent_class:
        logger.debug(
            "Rejecting parent_class with path traversal characters: %r",
            parent_class,
        )
        return None

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
        if direct.is_file() and _is_relative_to(direct, root):
            return direct
        if root.is_dir():
            try:
                match = next(
                    (
                        candidate
                        for candidate in root.rglob(target_name)
                        if _is_relative_to(candidate, root)
                    ),
                    None,
                )
            except OSError:
                match = None
            if match is not None and match.is_file():
                return match
    return None


def _package_metadata(bundle: Any) -> dict:
    """Extract package metadata from bundle."""
    return {
        "package_kind": bundle.package_kind,
        "package_files": bundle.package_files,
        "container": bundle.container,
        "asset_type_details": {},
    }


def _record_parse_stage_error(
    result: Any,
    archive: Optional["FArchive"],
    path: str,
    stage: str,
    field: str,
    error: Exception,
) -> None:
    """Record parse stage error to result."""
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
    result: Any,
    archive: Optional["FArchive"],
    path: str,
    tolerant: bool,
    stage: str,
    field: str,
    reader: Any,
):
    """Run required stage with error handling."""
    try:
        return reader()
    except Exception as e:
        from uasset_read.exceptions import VersionError, ParseError
        if not tolerant and isinstance(e, (VersionError, ParseError)):
            raise
        _record_parse_stage_error(result, archive, path, stage, field, e)
        return None


def _should_use_lightweight_tolerant_parse(
    result: Any,
    tolerant: bool,
    lightweight_threshold: Optional[int] = None,
) -> bool:
    """Check if lightweight tolerant parse should be used."""
    if not tolerant or result.summary is None:
        return False
    from uasset_read.constants import LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD
    threshold = (
        lightweight_threshold
        if lightweight_threshold is not None
        else LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD
    )
    return getattr(result.summary, "export_count", 0) > threshold


def _build_lightweight_function_graphs(export_map: Any) -> list[dict]:
    """Build lightweight function graphs for large assets."""
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
