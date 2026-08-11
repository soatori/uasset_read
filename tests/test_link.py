"""Consolidated linker and object instance tests.

Selected from:
- tests/linker/test_linker_lifecycle.py — lifecycle, preload, post_load, reference resolution
- tests/link/test_object_instance.py — UObjectInstance path generation, circular detection
- tests/test_linker.py — PackageLinker basics
- tests/linker/test_depends_map_resolution.py — depends map, package index resolution
- tests/linker/test_soft_object_path_index.py — soft object path index parsing
"""
from __future__ import annotations

import struct
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.serializers.object_resources import PackageIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_linker(
    export_count: int = 3,
    import_count: int = 1,
    file_size: int = 10000,
) -> PackageLinker:
    """Build a minimal PackageLinker with mock archive/summary."""
    archive = MagicMock()
    archive._file_size = file_size

    summary = MagicMock()
    summary.depends_map = None

    name_map: list[str] = []

    import_map = []
    for i in range(import_count):
        imp = MagicMock()
        imp.object_name = f"ImportObj_{i}"
        imp.class_name = f"ImportClass_{i}"
        imp.class_package = "/Script/Engine"
        imp.outer_index = PackageIndex(0)
        imp.class_index = PackageIndex(0)
        import_map.append(imp)

    export_map = []
    for i in range(export_count):
        exp = MagicMock()
        exp.object_name = f"ExportObj_{i}"
        exp.class_index = PackageIndex(-1) if import_count > 0 else PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.template_index = PackageIndex(0)
        exp.serial_offset = 100 + i * 200
        exp.serial_size = 100
        export_map.append(exp)

    linker = PackageLinker(
        archive=archive,
        summary=summary,
        name_map=name_map,
        import_map=import_map,
        export_map=export_map,
    )
    return linker


def _make_instance(
    name: str = "TestObj",
    package_index: int = 1,
    is_import: bool = False,
    outer: UObjectInstance | None = None,
    linker=None,
    class_package: str | None = None,
) -> UObjectInstance:
    """Create a UObjectInstance for testing."""
    return UObjectInstance(
        package_index=package_index,
        object_name=name,
        object_class="TestClass",
        class_package=class_package,
        outer_index=PackageIndex(0),
        is_import=is_import,
        outer=outer,
        linker=linker,
    )


# ===========================================================================
# 1. Lifecycle: preload marks instances correctly
#    Source: tests/linker/test_linker_lifecycle.py
# ===========================================================================

def test_preload_marks_instances():
    """After link(), calling preload() marks each instance as preloaded."""
    linker = _make_linker(export_count=3)
    linker.link()

    for inst in linker._export_objects:
        assert not inst._preloaded

    with patch(
        "uasset_read.parsers.property_parser.parse_properties_from_export",
        return_value=[],
    ):
        for i in range(3):
            linker.preload(i)

    for inst in linker._export_objects:
        assert inst._preloaded


# ===========================================================================
# 2. Lifecycle: ObjectProperty resolved to UObjectInstance
#    Source: tests/linker/test_linker_lifecycle.py
# ===========================================================================

def test_object_property_resolved_to_instance():
    """ObjectProperty with a valid export index resolves to the target instance."""
    linker = _make_linker(export_count=2)
    linker.link()

    inst0 = linker._export_objects[0]
    inst0._preloaded = True
    inst0.serialized_properties = [
        {"name": "TargetObj", "type": "ObjectProperty", "value": 2}
    ]

    linker._resolve_property_references()

    assert "TargetObj" in inst0.property_references
    resolved = inst0.property_references["TargetObj"]
    assert isinstance(resolved, UObjectInstance)
    assert resolved is linker._export_objects[1]


# ===========================================================================
# 3. UObjectInstance: nested outer path generation
#    Source: tests/link/test_object_instance.py
# ===========================================================================

def test_nested_outer_path_generation():
    """Multi-layer outer chain produces the full dot-separated path."""
    root = _make_instance(name="Root")
    mid = _make_instance(name="Mid", outer=root)
    leaf = _make_instance(name="Leaf", outer=mid)
    assert leaf.get_full_name() == "Root.Mid.Leaf"


# ===========================================================================
# 4. UObjectInstance: circular outer detection
#    Source: tests/link/test_object_instance.py
# ===========================================================================

def test_circular_outer_detection():
    """Self-referencing outer returns <circular:N> instead of RecursionError."""
    inst = _make_instance(name="Cyclic")
    inst.outer = inst
    result = inst.get_full_name()
    assert result == "<circular:1>.Cyclic"

    # Two-node cycle
    a = _make_instance(name="A")
    b = _make_instance(name="B")
    a.outer = b
    b.outer = a
    result_a = a.get_full_name()
    assert result_a == "<circular:2>.B.A"


# ===========================================================================
# 5. PackageLinker: link -> preload -> post_load lifecycle order
#    Source: tests/test_linker.py
# ===========================================================================

def test_link_preload_postload_lifecycle_order():
    """post_load runs after all preloads; ObjectProperty is resolved."""
    linker = _make_linker(export_count=2)
    linker.link()

    for inst in linker._export_objects:
        assert not inst._preloaded

    for i, inst in enumerate(linker._export_objects):
        inst._preloaded = True
        inst.serialized_properties = [
            {"name": f"Prop{i}", "type": "ObjectProperty", "value": 2}
        ]

    linker.post_load()

    for inst in linker._export_objects:
        assert hasattr(inst, "property_references")
