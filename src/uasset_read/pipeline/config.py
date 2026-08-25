"""Pipeline configuration — ParseConfig / LogConfig.

Extract scattered configuration parameters from parse_package() and core API into structured objects,
reducing function parameter count and improving readability and composability.
"""

from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.config import ParseConfig

from uasset_read.constants import (
    LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD,
    CONTROL_RIG_LARGE_FILE_THRESHOLD,
    CONTROL_RIG_LARGE_FILE_CLASSES,
)

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
    threshold = lightweight_threshold if lightweight_threshold is not None else LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD
    # Large files like ControlRig: detect export class names, use higher threshold
    if (
        threshold == LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD
        and lightweight_threshold is None
        and _is_large_file_asset(result)
    ):
        threshold = CONTROL_RIG_LARGE_FILE_THRESHOLD
    return getattr(result.summary, "export_count", 0) > threshold


def _is_large_file_asset(result) -> bool:
    """Detect whether the asset is a naturally large file like ControlRig/RigVM.

    Uses export class name substring matching to avoid misclassifying these assets
    as oversized blueprints.
    Reference: UE ControlRig.cpp serialization structure.
    """
    from uasset_read.serializers.object_resources import resolve_class_name

    export_map = getattr(result, "export_map", None) or []
    import_map = getattr(result, "import_map", None) or []
    # Only check first 20 exports' class names for detection (avoid full scan performance overhead)
    for export in export_map[:20]:
        try:
            class_name = resolve_class_name(export.class_index, import_map, export_map)
        except (AttributeError, TypeError, IndexError):
            continue
        if class_name and any(sub in class_name for sub in CONTROL_RIG_LARGE_FILE_CLASSES):
            return True
    return False


def _build_lightweight_graphs(result) -> list:
    """Extract basic graph information in lightweight mode (names only)."""
    from uasset_read.serializers.object_resources import get_asset_class
    from uasset_read.models.core import UEdGraph

    graphs = []
    if not result.export_map or not result.import_map:
        return graphs

    for export in result.export_map:
        name = str(getattr(export, "object_name", "") or "")
        if not name:
            continue

        # Detect EdGraph type exports
        class_name = get_asset_class(export, result.import_map, result.export_map)
        if class_name in ("EdGraph", "UberEdGraph"):
            # Create minimal UEdGraph with name only
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
        entries.append(
            {
                "function_name": name,
                "graph_source": "export_map",
                "entry_node_guid": "",
                "signature": {"return_type": "", "parameters": []},
                "execution_flows": [],
                "fallback_reason": "lightweight_tolerant_parse",
            }
        )
        if len(entries) >= 64:
            break
    return entries


def _apply_lightweight_parse(
    result,
    tolerant: bool,
    lightweight_threshold: int | None,
    force_full_parse: bool,
) -> bool:
    """Lightweight parse path: if triggered, populates result and returns True."""
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


def _resolve_parse_params(
    config: ParseConfig | None,
    kwargs: dict,
) -> dict:
    """Merge ParseConfig and legacy-style keyword arguments into final parameter dict.

    - If config is provided, config values serve as defaults; explicitly passed legacy parameters can override.
    - If config is not provided, legacy parameters remain as-is.
    - Issues DeprecationWarning when values are passed from both config and legacy parameters.

    kwargs entries with None values are treated as "caller not specified" and do not override config values.
    """
    if config is None:
        return kwargs

    # All legacy parameters in parse_package() signature default to None (sentinel);
    # only non-None values explicitly passed by the caller count as "explicit override".
    # But if the caller explicitly passes a non-None value different from config value,
    # issue a deprecation warning.
    conflicting = []
    for fld in config.__dataclass_fields__:
        if fld in kwargs and kwargs[fld] is not None:
            config_val = getattr(config, fld)
            if config_val is not None and kwargs[fld] != config_val:
                conflicting.append(fld)

    if conflicting:
        warnings.warn(
            f"Both config and legacy parameters {conflicting} were passed; legacy parameters will override corresponding config values. "
            "Please use ParseConfig exclusively.",
            DeprecationWarning,
            stacklevel=3,
        )

    # Merge: non-None kwargs values override config, None values do not override
    merged = {}
    for fld in config.__dataclass_fields__:
        kw_val = kwargs.get(fld)
        merged[fld] = kw_val if kw_val is not None else getattr(config, fld)
    # Keep keys in kwargs that are not in config (e.g., path, provider, etc.)
    for key in kwargs:
        if key not in merged:
            merged[key] = kwargs[key]
    return merged
