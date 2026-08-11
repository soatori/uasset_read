"""Consolidated UObject and material property tests."""
from __future__ import annotations

import pytest

from uasset_read.objects.registry import ObjectTypeRegistry, global_registry
from uasset_read.objects.uobject import UObject


class TestObjectTypeRegistry:
    """ObjectTypeRegistry registration and lookup."""

    def test_decorator_register_and_get_class(self):
        """Registering via decorator makes the class findable via get_class."""
        registry = ObjectTypeRegistry()

        @registry.register("MyCustomClass")
        class UMyCustomClass(UObject):
            pass

        found = registry.get_class("MyCustomClass")
        assert found is UMyCustomClass


class TestUObjectBasic:
    """UObject basic construction and property access."""

    def test_uobject_creation_and_properties(self):
        """UObject sets attributes correctly and supports get/set."""
        obj = UObject(name="TestObject")
        assert obj.name == "TestObject"
        assert obj.flags == 0
        assert obj.outer is None
        obj.set_property("CustomData", 42)
        assert obj.get_property("CustomData") == 42
        assert obj.get_property("Missing", "default") == "default"


class TestMaterialParameters:
    """Material parameter extraction helpers."""

    def test_collect_parameters_extracts_association(self):
        """_collect_parameters should extract Association and Index fields."""
        from uasset_read.objects.exports.material import _collect_parameters

        source = [
            {
                "ParameterInfo": {"Name": "BaseColor", "Association": 0, "Index": -1},
                "ParameterValue": [1.0, 0.0, 0.0, 1.0],
            }
        ]
        result = _collect_parameters(source, value_names=("ParameterValue",))
        assert "BaseColor" in result
        assert result["BaseColor"]["association"] == 0
        assert result["BaseColor"]["index"] == -1
