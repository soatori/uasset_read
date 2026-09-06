"""Agent tools for package inspection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .package import parse_package_document
from .projection import project_document


def inspect_package(
    file_path: str | Path,
    *,
    depth: str = "asset",
    object_ids: list[str] | None = None,
    roles: list[str] | None = None,
    classes: list[str] | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> dict[str, Any]:
    """Inspect a .uasset/.umap file and return structured information.

    This is the primary agent tool for package inspection.
    """
    doc = parse_package_document(
        file_path,
        depth=depth,
        object_ids=object_ids,
    )
    return project_document(
        doc,
        depth=depth,
        object_ids=object_ids,
        roles=roles,
        classes=classes,
        offset=offset,
        limit=limit,
    )


def inspect_package_json(
    file_path: str | Path,
    **kwargs: Any,
) -> str:
    """Inspect a package and return JSON string."""
    result = inspect_package(file_path, **kwargs)
    return json.dumps(result, indent=2, ensure_ascii=False)
