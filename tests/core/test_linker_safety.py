"""Regression tests for PackageLinker safety guards.

Covers:
- resolve_package_index bounds validation (export and import)
- preload serial_offset / serial_size validation
- _verify_imports class_name bounds checking
- UObjectInstance.get_full_name circular outer reference detection
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_linker(
    export_count: int = 0,
    import_count: int = 0,
    file_size: int = 10_000,
) -> PackageLinker:
    """Create a PackageLinker with synthetic objects, bypassing __init__."""
    linker = object.__new__(PackageLinker)
    linker._archive = MagicMock()
    linker._summary = MagicMock()
    linker._name_map = [f"Name_{i}" for i in range(20)]
    linker._import_map = []
    linker._export_map = []
    linker._version_container = None
    linker.summary = linker._summary
    linker.name_map = linker._name_map
    linker.version_container = None
    linker._import_verification_errors = []

    from uasset_read.bounded_events import BoundedEventBuffer
    linker._diagnostics = BoundedEventBuffer(max_entries=10000)
    linker._file_size = file_size
    linker._preload_cache = {}
    linker._root_objects = []

    # Create export objects and export map entries
    linker._export_objects = []
    linker._export_map = []
    for i in range(export_count):
        exp = ObjectExport(
            class_index=PackageIndex(0),
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name=f"Export_{i}",
            object_flags=0,
            serial_size=100,
            serial_offset=0,
        )
        linker._export_map.append(exp)
        obj = UObjectInstance(
            package_index=i + 1,
            object_name=f"Export_{i}",
            object_class="Object",
            class_package=None,
            outer_index=PackageIndex(0),
            is_import=False,
            serial_offset=0,
            serial_size=100,
            linker=linker,
            _raw_export=exp,
        )
        linker._export_objects.append(obj)

    # Create import objects
    linker._import_objects = []
    for i in range(import_count):
        obj = UObjectInstance(
            package_index=-(i + 1),
            object_name=f"Import_{i}",
            object_class="Class",
            class_package="/Script/Engine",
            outer_index=PackageIndex(0),
            is_import=True,
            linker=linker,
        )
        linker._import_objects.append(obj)

    return linker


# ---------------------------------------------------------------------------
# Test: resolve_package_index
# ---------------------------------------------------------------------------

def test_resolve_null_index_returns_none():
    """resolve_package_index(None-like) with null PackageIndex returns None."""
    linker = _make_linker(export_count=3)
    result = linker.resolve_package_index(PackageIndex(0))
    assert result is None


def test_resolve_valid_export_index():
    """resolve_package_index returns the correct UObjectInstance for a valid export index."""
    linker = _make_linker(export_count=3)
    # PackageIndex(1) = export index 0
    result = linker.resolve_package_index(PackageIndex(1))
    assert result is not None
    assert result.object_name == "Export_0"

    # PackageIndex(3) = export index 2
    result = linker.resolve_package_index(PackageIndex(3))
    assert result is not None
    assert result.object_name == "Export_2"


def test_resolve_valid_import_index():
    """resolve_package_index returns the correct UObjectInstance for a valid import index."""
    linker = _make_linker(import_count=2)
    # PackageIndex(-1) = import index 0
    result = linker.resolve_package_index(PackageIndex(-1))
    assert result is not None
    assert result.object_name == "Import_0"


def test_resolve_out_of_bounds_export_records_diagnostic():
    """resolve_package_index records diagnostic for out-of-bounds export index."""
    linker = _make_linker(export_count=2)
    # PackageIndex(5) = export index 4, but we only have 2 exports
    result = linker.resolve_package_index(PackageIndex(5))
    assert result is None
    # Verify diagnostic was recorded
    diagnostics = linker.diagnostics
    assert len(diagnostics) >= 1
    assert "out of bounds" in diagnostics[-1].error


def test_resolve_out_of_bounds_import_records_diagnostic():
    """resolve_package_index records diagnostic for out-of-bounds import index."""
    linker = _make_linker(import_count=2)
    # PackageIndex(-5) = import index 4, but we only have 2 imports
    result = linker.resolve_package_index(PackageIndex(-5))
    assert result is None
    diagnostics = linker.diagnostics
    assert len(diagnostics) >= 1
    assert "out of bounds" in diagnostics[-1].error


# ---------------------------------------------------------------------------
# Test: preload validation
# ---------------------------------------------------------------------------

def test_preload_negative_serial_size_records_diagnostic():
    """preload() records diagnostic and marks instance when serial_size is negative."""
    linker = _make_linker(export_count=1, file_size=10_000)
    linker._export_objects[0].serial_size = -1
    linker._export_objects[0].serial_offset = 100

    linker.preload(0)

    # Should not crash; instance should be marked as preloaded
    assert linker._export_objects[0]._preloaded is True
    diagnostics = linker.diagnostics
    assert len(diagnostics) >= 1
    assert "negative" in diagnostics[-1].error


def test_preload_offset_plus_size_exceeds_file_records_diagnostic():
    """preload() records diagnostic when serial_offset + serial_size > file_size."""
    linker = _make_linker(export_count=1, file_size=100)
    linker._export_objects[0].serial_offset = 80
    linker._export_objects[0].serial_size = 50  # 80 + 50 = 130 > 100

    linker.preload(0)

    assert linker._export_objects[0]._preloaded is True
    diagnostics = linker.diagnostics
    assert len(diagnostics) >= 1
    assert "exceeds file size" in diagnostics[-1].error


# ---------------------------------------------------------------------------
# Test: _verify_imports
# ---------------------------------------------------------------------------

def test_verify_imports_out_of_bounds_class_name():
    """_verify_imports() detects class_name index out of bounds in name_map."""
    linker = _make_linker(import_count=1)
    # Set class_name to an int index beyond name_map length
    imp = MagicMock()
    imp.class_name = 999  # beyond linker._name_map range
    imp.outer_index = PackageIndex(0)
    imp.object_name = "BadImport"
    linker._import_map = [imp]

    errors = linker._verify_imports()
    assert any("out of bounds" in e for e in errors)


# ---------------------------------------------------------------------------
# Test: UObjectInstance.get_full_name circular detection
# ---------------------------------------------------------------------------

def test_get_full_name_self_referencing_cycle():
    """get_full_name() returns '<circular:...>' when an object's outer is itself."""
    obj = UObjectInstance(
        package_index=1,
        object_name="SelfRef",
        object_class="Object",
        class_package=None,
        outer_index=None,
        is_import=False,
    )
    obj.outer = obj  # self-reference

    result = obj.get_full_name()
    assert "<circular:" in result


def test_get_full_name_two_node_cycle():
    """get_full_name() returns '<circular:...>' for a two-node outer cycle."""
    obj_a = UObjectInstance(
        package_index=1,
        object_name="ObjA",
        object_class="Object",
        class_package=None,
        outer_index=None,
        is_import=False,
    )
    obj_b = UObjectInstance(
        package_index=2,
        object_name="ObjB",
        object_class="Object",
        class_package=None,
        outer_index=None,
        is_import=False,
    )
    obj_a.outer = obj_b
    obj_b.outer = obj_a

    result = obj_a.get_full_name()
    assert "<circular:" in result
    assert "ObjA" in result


def test_get_full_name_three_node_cycle():
    """get_full_name() returns '<circular:...>' for a three-node outer cycle."""
    obj_a = UObjectInstance(
        package_index=1, object_name="A", object_class=None,
        class_package=None, outer_index=None, is_import=False,
    )
    obj_b = UObjectInstance(
        package_index=2, object_name="B", object_class=None,
        class_package=None, outer_index=None, is_import=False,
    )
    obj_c = UObjectInstance(
        package_index=3, object_name="C", object_class=None,
        class_package=None, outer_index=None, is_import=False,
    )
    obj_a.outer = obj_b
    obj_b.outer = obj_c
    obj_c.outer = obj_a

    result = obj_a.get_full_name()
    assert "<circular:" in result


def test_get_full_name_no_cycle_returns_normal_path():
    """get_full_name() returns correct dotted path when there is no cycle."""
    obj_root = UObjectInstance(
        package_index=0, object_name="Root", object_class=None,
        class_package=None, outer_index=None, is_import=True,
    )
    obj_mid = UObjectInstance(
        package_index=1, object_name="Middle", object_class=None,
        class_package=None, outer_index=None, is_import=False,
        outer=obj_root,
    )
    obj_leaf = UObjectInstance(
        package_index=2, object_name="Leaf", object_class=None,
        class_package=None, outer_index=None, is_import=False,
        outer=obj_mid,
    )

    result = obj_leaf.get_full_name()
    assert result == "Root.Middle.Leaf"
    assert "<circular:" not in result
