"""Deterministic UTF-8 JSON writer over the v4 package-output producer.

``write_projected_document`` serializes exactly the dict returned by
``project_document()``. Capability status rides each projection record
(status/completeness); the matrix itself stays on
``uasset_read.projections.registry.CAPABILITY_MATRIX``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from uasset_read.models.document import PackageDocument
from uasset_read.projection import project_document


def _serialize_canonical(payload: dict[str, Any]) -> str:
    """Deterministic compact UTF-8 JSON encoding used for the file write."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def write_projected_document(
    document: PackageDocument,
    output_path: Path,
    *,
    mode: Literal["normal", "debug"] = "normal",
) -> Path:
    """Write one UTF-8 JSON document equal to ``project_document(document, mode=mode)``."""
    payload = project_document(document, mode=mode)
    output_path = Path(output_path)
    output_path.write_text(_serialize_canonical(payload), encoding="utf-8")
    return output_path
