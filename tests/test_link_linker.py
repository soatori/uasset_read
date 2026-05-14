"""Tests for PackageLinker core class."""

import pytest
from unittest.mock import MagicMock, patch

from uasset_read.serializers.object_resources import (
    PackageIndex, ObjectImport, ObjectExport,
)
from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance


def _make_linker(import_entries=None, export_entries=None, name_map=None):
    if name_map is None:
        name_map = ["TestPackage", "MyClass", "MyObject", "ParentClass"]
    if import_entries is None:
        import_entries = [ObjectImport(
            class_package=name_map[0],
            class_name=name_map[1],
            outer_index=PackageIndex(0),
            object_name=name_map[2],
        )]
    if export_entries is None:
        export_entries = [
            ObjectExport(
                class_index=PackageIndex(-1),
                super_index=PackageIndex(0),
                outer_index=PackageIndex(0),
                object_name=name_map[2],
                object_flags=0,
                serial_size=0,
                serial_offset=0,
            ),
        ]
    archive = MagicMock()
    summary = MagicMock()
    return PackageLinker(archive, summary, name_map, import_entries, export_entries), archive


class TestPackageLinkerLink:
    def test_link_creates_export_instances(self):
        linker, _ = _make_linker(export_entries=[
            ObjectExport(class_index=PackageIndex(-1), super_index=PackageIndex(0), outer_index=PackageIndex(0), object_name="Exp1", object_flags=0, serial_size=10, serial_offset=0),
            ObjectExport(class_index=PackageIndex(-1), super_index=PackageIndex(0), outer_index=PackageIndex(0), object_name="Exp2", object_flags=0, serial_size=20, serial_offset=100),
        ])
        linker.link()
        assert len(linker._export_objects) == 2

    def test_link_creates_import_instances(self):
        linker, _ = _make_linker(import_entries=[ObjectImport(class_package="Pkg", class_name="Cls", outer_index=PackageIndex(0), object_name="Imp1")])
        linker.link()
        assert len(linker._import_objects) == 1

    def test_link_sets_linker_reference(self):
        linker, _ = _make_linker()
        linker.link()
        assert linker._export_objects[0].linker is linker
        assert linker._import_objects[0].linker is linker

    def test_link_sets_serial_info(self):
        linker, _ = _make_linker(export_entries=[ObjectExport(class_index=PackageIndex(-1), super_index=PackageIndex(0), outer_index=PackageIndex(0), object_name="Exp1", object_flags=0, serial_size=100, serial_offset=500)])
        linker.link()
        inst = linker._export_objects[0]
        assert inst.serial_offset == 500
        assert inst.serial_size == 100


class TestPackageLinkerResolve:
    def test_resolve_export(self):
        linker, _ = _make_linker()
        linker.link()
        assert linker.resolve_package_index(PackageIndex(1)) is linker._export_objects[0]

    def test_resolve_import(self):
        linker, _ = _make_linker()
        linker.link()
        assert linker.resolve_package_index(PackageIndex(-1)) is linker._import_objects[0]

    def test_resolve_null(self):
        linker, _ = _make_linker()
        linker.link()
        assert linker.resolve_package_index(PackageIndex(0)) is None

    def test_resolve_out_of_bounds(self):
        linker, _ = _make_linker()
        linker.link()
        assert linker.resolve_package_index(PackageIndex(999)) is None

    def test_resolve_import_out_of_bounds(self):
        linker, _ = _make_linker()
        linker.link()
        assert linker.resolve_package_index(PackageIndex(-999)) is None


class TestPackageLinkerOuterTree:
    def test_outer_tree_resolves_parent(self):
        export_entries = [
            ObjectExport(class_index=PackageIndex(-1), super_index=PackageIndex(0), outer_index=PackageIndex(0), object_name="Parent", object_flags=0, serial_size=0, serial_offset=0),
            ObjectExport(class_index=PackageIndex(-1), super_index=PackageIndex(0), outer_index=PackageIndex(1), object_name="Child", object_flags=0, serial_size=0, serial_offset=0),
        ]
        linker, _ = _make_linker(export_entries=export_entries)
        linker.link()
        assert linker._export_objects[1].outer is linker._export_objects[0]

    def test_outer_null_keeps_outer_none(self):
        linker, _ = _make_linker(export_entries=[ObjectExport(class_index=PackageIndex(-1), super_index=PackageIndex(0), outer_index=PackageIndex(0), object_name="Root", object_flags=0, serial_size=0, serial_offset=0)])
        linker.link()
        assert linker._export_objects[0].outer is None


class TestPackageLinkerGetChildren:
    def test_get_children_returns_correct_list(self):
        export_entries = [
            ObjectExport(class_index=PackageIndex(-1), super_index=PackageIndex(0), outer_index=PackageIndex(0), object_name="Parent", object_flags=0, serial_size=0, serial_offset=0),
            ObjectExport(class_index=PackageIndex(-1), super_index=PackageIndex(0), outer_index=PackageIndex(1), object_name="Child1", object_flags=0, serial_size=0, serial_offset=0),
            ObjectExport(class_index=PackageIndex(-1), super_index=PackageIndex(0), outer_index=PackageIndex(1), object_name="Child2", object_flags=0, serial_size=0, serial_offset=0),
        ]
        linker, _ = _make_linker(export_entries=export_entries)
        linker.link()
        parent = linker._export_objects[0]
        children = linker.get_children(parent)
        assert len(children) == 2
        assert children[0].object_name == "Child1"
        assert children[1].object_name == "Child2"

    def test_get_children_no_children(self):
        linker, _ = _make_linker()
        linker.link()
        assert linker.get_children(linker._export_objects[0]) == []


class TestPackageLinkerPreload:
    def _make_preload_linker(self, serial_size=100):
        export_entries = [ObjectExport(class_index=PackageIndex(-1), super_index=PackageIndex(0), outer_index=PackageIndex(0), object_name="Exp", object_flags=0, serial_size=serial_size, serial_offset=50)]
        linker, archive = _make_linker(export_entries=export_entries)
        linker.link()
        return linker, archive

    def test_preload_sets_flag(self):
        linker, archive = self._make_preload_linker()
        with patch("uasset_read.parsers.property_parser.parse_properties_from_export", return_value=[MagicMock()]):
            linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        archive.seek.assert_called_once_with(50)

    def test_preload_idempotent(self):
        linker, archive = self._make_preload_linker()
        with patch("uasset_read.parsers.property_parser.parse_properties_from_export", return_value=[MagicMock()]) as mock_parse:
            linker.preload(0)
            linker.preload(0)
        assert mock_parse.call_count == 1
        assert len(linker._export_objects[0].serialized_properties) == 1

    def test_preload_zero_size(self):
        linker, archive = self._make_preload_linker(serial_size=0)
        linker.preload(0)
        assert linker._export_objects[0]._preloaded is True
        archive.seek.assert_not_called()
        assert linker._export_objects[0].serialized_properties == []

    def test_preload_out_of_bounds(self):
        linker, _ = self._make_preload_linker()
        linker.preload(-1)
        linker.preload(999)
        assert 0 not in linker._preload_cache

    def test_preload_cache_used(self):
        linker, archive = self._make_preload_linker()
        with patch("uasset_read.parsers.property_parser.parse_properties_from_export", return_value=[MagicMock()]) as mock_parse:
            linker.preload(0)
            assert 0 in linker._preload_cache
            linker.preload(0)
        assert mock_parse.call_count == 1
