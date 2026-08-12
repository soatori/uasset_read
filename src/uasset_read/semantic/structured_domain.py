"""Structured domain extractor — returns plain dict, not ContentNode."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import ExportIR
    from uasset_read.semantic.coverage import CoverageModel
    from uasset_read.semantic.models import EvidenceEntry


def _dict_to_plain(data: Any) -> Any:
    """Recursively convert dicts and lists to plain Python types.

    Ensures all values are JSON-serializable primitives (str, int, float,
    bool, None) nested in plain dicts and lists.
    """
    if isinstance(data, dict):
        return {k: _dict_to_plain(v) for k, v in sorted(data.items())}
    if isinstance(data, list):
        return [_dict_to_plain(item) for item in data]
    return data


def extract_structured(export: ExportIR, coverage: CoverageModel, evidence_list: list[EvidenceEntry] | None = None) -> dict:
    """Extract structured metadata for non-Blueprint asset types.

    Handles StaticMesh, Skeleton, AnimSequence, DataTable assets and any
    export that carries ``asset_type_data``.  Returns a plain dict suitable
    for ``SemanticIR.content``.

    Coverage scopes tracked:
    - ``structured_metadata`` — class_name, object_name, serial_size
    - ``asset_type_data``     — present when export.asset_type_data is not None
    - ``skeleton_data``       — present when reference_skeleton exists in asset_type_data
    - ``row_data``            — present when rows exists in asset_type_data
    """
    result: dict[str, Any] = {}

    # --- structured_metadata (always available) ---
    result["class_name"] = export.object_class
    result["object_name"] = export.object_name
    result["serial_size"] = export.serial_size
    coverage.track("structured_metadata", True)

    # --- asset_type_data (optional) ---
    atd = export.asset_type_data
    atd_present = atd is not None and len(atd) > 0
    coverage.track("asset_type_data", atd_present)

    if atd_present:
        # parse_status pass-through
        if "parse_status" in atd:
            result["parse_status"] = atd["parse_status"]

        # reference_skeleton — convert recursively to plain dict
        ref_skel = atd.get("reference_skeleton")
        skeleton_available = ref_skel is not None and len(ref_skel) > 0
        coverage.track("skeleton_data", skeleton_available)
        if skeleton_available:
            result["reference_skeleton"] = _dict_to_plain(ref_skel)

        # retarget_sources — convert recursively to plain dict
        retarget = atd.get("retarget_sources")
        if retarget is not None and len(retarget) > 0:
            result["retarget_sources"] = _dict_to_plain(retarget)

        # row_data (DataTable rows) — emit row_count only, rows too large to inline
        rows = atd.get("rows")
        row_available = rows is not None
        coverage.track("row_data", row_available)
        if row_available:
            result["row_count"] = len(rows)

        # row_count explicit field (may differ from len(rows))
        if "row_count" in atd and "row_count" not in result:
            result["row_count"] = atd["row_count"]

        # guid pass-through
        if "guid" in atd:
            result["guid"] = atd["guid"]
    else:
        # Track remaining scopes as unavailable
        coverage.track("skeleton_data", False)
        coverage.track("row_data", False)

    return result
