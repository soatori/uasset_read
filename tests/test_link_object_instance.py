"""Tests for UObjectInstance dataclass and helper methods."""

import pytest
from uasset_read.link.object_instance import UObjectInstance


class TestUObjectInstance:
    """UObjectInstance field and behavior tests."""

    def test_creation_export(self):
        """Create an export instance and verify fields."""
        inst = UObjectInstance(
            package_index=1,
            object_name="Test",
            object_class="TestClass",
            class_package="/Script/Engine",
            outer_index=None,
            is_import=False,
        )
        assert inst.package_index == 1
        assert inst.object_name == "Test"
        assert inst.object_class == "TestClass"
        assert inst.is_import is False
        assert inst.is_export is True

    def test_is_null(self):
        """package_index=0 means null."""
        inst = UObjectInstance(
            package_index=0,
            object_name="None",
            object_class=None,
            class_package=None,
            outer_index=None,
            is_import=False,
        )
        assert inst.is_null is True

    def test_is_not_null(self):
        """Non-zero package_index is not null."""
        inst = UObjectInstance(
            package_index=1,
            object_name="Test",
            object_class="TestClass",
            class_package=None,
            outer_index=None,
            is_import=False,
        )
        assert inst.is_null is False

    def test_get_full_name_no_outer(self):
        """get_full_name returns object_name when no outer."""
        inst = UObjectInstance(
            package_index=1,
            object_name="MyObject",
            object_class="EdGraph",
            class_package=None,
            outer_index=None,
            is_import=False,
        )
        full = inst.get_full_name()
        assert "MyObject" in full

    def test_repr_export(self):
        """__repr__ includes 'Export' keyword for export instances."""
        inst = UObjectInstance(
            package_index=1,
            object_name="Test",
            object_class="TestClass",
            class_package=None,
            outer_index=None,
            is_import=False,
        )
        assert "Export" in repr(inst)

    def test_repr_import(self):
        """__repr__ includes 'Import' keyword for import instances."""
        inst = UObjectInstance(
            package_index=-1,
            object_name="Test",
            object_class="TestClass",
            class_package="/Script/Core",
            outer_index=None,
            is_import=True,
        )
        assert "Import" in repr(inst)

    def test_is_export_for_import(self):
        """is_export returns False when is_import=True."""
        inst = UObjectInstance(
            package_index=-1,
            object_name="Test",
            object_class="TestClass",
            class_package="/Script/Core",
            outer_index=None,
            is_import=True,
        )
        assert inst.is_export is False
