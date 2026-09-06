"""Resolve parent assets across packages for Blueprint inheritance.

Locates parent class packages on disk using import maps and soft object
paths, parses them, and extracts class declarations for inheritance chains.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.document import PackageDocument

logger = logging.getLogger(__name__)


def resolve_parent_assets(
    doc: PackageDocument,
    root: Path,
    max_depth: int = 2,
) -> tuple[list[dict], list[Diagnostic]]:
    """Resolve parent class/interface assets across packages.

    Args:
        doc: The PackageDocument to resolve parents for.
        root: Root directory to search for parent packages.
        max_depth: Maximum recursion depth for cross-package resolution.

    Returns:
        Tuple of (relations, diagnostics) to add to doc.relations and doc.diagnostics.
    """
    from uasset_read.models.diagnostics import Diagnostic

    relations = []
    diagnostics = []

    # Find Blueprint objects with parent references
    for obj in doc.objects:
        sem = getattr(obj, "semantic", None) or {}
        if sem.get("kind") != "blueprint":
            continue

        parent_ref = sem.get("parent_class")
        if not parent_ref or parent_ref == "UObject":
            continue

        # Try to locate the parent package on disk
        parent_path = _find_parent_package(parent_ref, root, max_depth)
        if parent_path is None:
            diagnostics.append(
                Diagnostic(
                    severity="info",
                    code="PARENT_NOT_FOUND",
                    message=f"Parent class package for '{parent_ref}' not found under {root}",
                    stage="parent_resolution",
                )
            )
            continue

        # Parse the parent package (at package depth to avoid deep recursion)
        try:
            from uasset_read.package import parse_package_document

            parent_doc = parse_package_document(
                str(parent_path), depth="package", tolerant=True
            )
            relations.append(
                {
                    "kind": "parent_class",
                    "source": obj.id,
                    "target": parent_ref,
                    "target_package": str(parent_path),
                }
            )
        except Exception as e:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="PARENT_PARSE_FAILED",
                    message=f"Failed to parse parent package '{parent_path}': {e}",
                    stage="parent_resolution",
                )
            )

    return relations, diagnostics


def _find_parent_package(class_name: str, root: Path, max_depth: int) -> Path | None:
    """Find a .uasset file on disk that might contain class_name.

    Searches by:
    1. Exact class name match: {class_name}.uasset
    2. BlueprintGeneratedClass suffix: {class_name}.BlueprintGeneratedClass.uasset
    3. Recursive search under root (bounded by max_depth)
    """
    # Try exact match
    exact = root / f"{class_name}.uasset"
    if exact.exists():
        return exact

    # Try BlueprintGeneratedClass suffix
    bgc = root / f"{class_name}.BlueprintGeneratedClass.uasset"
    if bgc.exists():
        return bgc

    # Bounded recursive search (controlled by max_depth)
    for depth in range(1, max_depth + 1):
        for path in root.rglob(f"{class_name}.uasset"):
            # Check depth relative to root
            rel = path.relative_to(root)
            if len(rel.parts) <= depth + 1:
                return path
        for path in root.rglob(f"{class_name}*.uasset"):
            rel = path.relative_to(root)
            if len(rel.parts) <= depth + 1:
                return path

    return None
