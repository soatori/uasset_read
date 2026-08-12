"""Resource domain extractor — Texture2D / SoundWave metadata.

Returns a plain dict (no ContentNode) that becomes ``SemanticIR.content``.
Tracks three coverage scopes: ``resource_metadata``, ``resource_properties``,
and ``asset_type_data``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import ExportIR
    from uasset_read.semantic.coverage import CoverageModel
    from uasset_read.semantic.models import EvidenceEntry

# Property keys considered resource-relevant (Texture2D / SoundWave).
_RESOURCE_PROPERTY_KEYS: frozenset[str] = frozenset({
    "SizeX",
    "SizeY",
    "SizeZ",
    "NumMips",
    "Format",
    "bHasAlphaChannel",
    "SRGB",
    "LODGroup",
    "SampleRate",
    "NumChannels",
    "Duration",
})


def extract_resource(export: ExportIR, coverage: CoverageModel, evidence_list: list[EvidenceEntry] | None = None) -> dict:
    """Extract resource-relevant data from *export*.

    Parameters
    ----------
    export:
        The export intermediate representation.
    coverage:
        Coverage tracker — called with ``track()`` for every data scope
        this extractor attempts to populate.
    evidence_list:
        Optional mutable list for debug evidence entries.

    Returns
    -------
    dict
        Deterministic, sorted-key dictionary ready for ``SemanticIR.content``.
    """
    result: dict = {}

    # ── resource_metadata (always available) ──────────────────────────
    result["class_name"] = export.object_class
    result["object_name"] = export.object_name
    result["serial_size"] = export.serial_size
    coverage.track("resource_metadata", True)

    # ── resource_properties ───────────────────────────────────────────
    props = {p.name: p.value for p in export.properties}
    resource_props: dict = {}
    for key in sorted(_RESOURCE_PROPERTY_KEYS):
        if key in props:
            resource_props[key] = props[key]

    if resource_props:
        result["properties"] = resource_props
        coverage.track("resource_properties", True)
    else:
        coverage.track("resource_properties", False)

    # ── asset_type_data ───────────────────────────────────────────────
    atd = export.asset_type_data
    if atd:
        atd_slice: dict = {}
        for key in ("parse_status", "raw_offset", "sample_size"):
            if key in atd:
                atd_slice[key] = atd[key]
        if atd_slice:
            result["asset_type_data"] = atd_slice
        coverage.track("asset_type_data", True)
    else:
        coverage.track("asset_type_data", False)

    return result
