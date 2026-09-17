"""Ordinary named sample/parser helpers shared by tests (plan File Map).

These are plain functions, not pytest fixtures: tests import them from
``tests.fixtures``.  Pytest-discoverable fixtures live in ``tests/conftest.py``.
"""

from __future__ import annotations

from pathlib import Path

from uasset_read.models.document import PackageDocument
from uasset_read.models.object_model import ObjectRecord
from uasset_read.package import parse_package_document

SAMPLES = Path(__file__).resolve().parent / "samples"


def sample_path(name: str) -> Path:
    path = SAMPLES / name
    if not path.exists():
        raise FileNotFoundError(f"missing fixture sample: {name}")
    return path


def parse_sample(
    name: str,
    *,
    depth: str = "decode",
    object_ids: list[str] | None = None,
) -> PackageDocument:
    return parse_package_document(
        sample_path(name),
        depth=depth,
        object_ids=object_ids,
        tolerant=True,
    )


def find_function(document: PackageDocument, name: str):
    """Return the projected function dict for `name` (E1: dicts, not dataclasses)."""
    for obj in document.objects:
        for fn in ((obj.semantic or {}).get("functions") or []):
            if fn.get("function_name") == name:
                return fn
    raise KeyError(f"function not found: {name}")


def find_blueprint_object(document: PackageDocument) -> ObjectRecord:
    for obj in document.objects:
        if "asset" in obj.roles and (obj.semantic or {}).get("kind") in {"blueprint", "anim_blueprint"}:
            return obj
    raise KeyError("no blueprint asset object in document")


def find_material_graph(document: PackageDocument) -> dict:
    """Return the projected material_graph dict (E1), never a live MaterialGraph dataclass."""
    for obj in document.objects:
        graph = (obj.semantic or {}).get("material_graph")
        if isinstance(graph, dict) and graph.get("expressions") is not None:
            return graph
    raise KeyError("no material graph in document")


def make_property_input(name: str, *, object_name: str | None = None):
    # Imports are lazy so Task 1 can create this helper before Tasks 2/4 add
    # the bounded source and property-input models.
    from uasset_read.parsers.properties import PropertyInput
    from uasset_read.sources import CompositeSource
    from uasset_read.versioning import VersionContext

    path = sample_path(name)
    document = parse_package_document(path, depth="package", tolerant=True)
    candidates = [obj for obj in document.objects if obj.serial_region and obj.serial_region.size > 0]
    obj = next((item for item in candidates if item.name == object_name), candidates[0])
    return PropertyInput(
        source=CompositeSource.from_package(path),
        object_id=obj.id,
        start=obj.serial_region.offset,
        size=obj.serial_region.size,
        class_name=obj.class_name or "Unknown",
        context=VersionContext(depth="object"),
    )
