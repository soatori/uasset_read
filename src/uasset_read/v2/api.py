"""Public v2 API — parse to PackageDocument.

Direct binary reader for legacy packages, no v1 pipeline dependency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Sequence

from .document import PackageDocument
from .package.legacy import LegacyPackageReader
from .source import FileSource


def parse_package_document(
    file_path: str | Path,
    *,
    tolerant: bool = True,
    mappings_path: str | None = None,
    game: str | None = None,
    depth: Literal["package", "object", "asset", "decode"] = "asset",
    object_ids: Sequence[str] | None = None,
) -> PackageDocument:
    """Parse a .uasset/.umap and return a v2 PackageDocument.

    Reads the binary format directly using LegacyPackageReader.
    """
    source = FileSource(file_path)
    reader = LegacyPackageReader(
        source,
        tolerant=tolerant,
        mappings_path=mappings_path,
        game=game,
    )
    return reader.read(depth=depth, object_ids=object_ids)
