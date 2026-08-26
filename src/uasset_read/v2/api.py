"""Public v2 API — parse to PackageDocument.

Thin wrappers that call the v1 pipeline and convert results
to the v2 PackageDocument model.
"""

from __future__ import annotations

from pathlib import Path

from .document import PackageDocument
from .package import build_package_document


def parse_package_document(
    file_path: str | Path,
    *,
    tolerant: bool = True,
    mappings_path: str | None = None,
    game: str | None = None,
) -> PackageDocument:
    """Parse a .uasset/.umap and return a v2 PackageDocument.

    Uses the v1 pipeline under the hood, then converts to v2.
    """
    from ..pipeline.core import parse_uasset_with_linker

    path = str(file_path)
    result = parse_uasset_with_linker(
        path,
        tolerant=tolerant,
        mappings_path=mappings_path,
        game=game,
    )
    return build_package_document(result, path)
