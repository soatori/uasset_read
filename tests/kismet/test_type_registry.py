"""TypeRegistry tests — UE → C++ type mapping and metadata population."""
import pytest
from uasset_read.kismet.translator import TypeRegistry


class TestTypeRegistryBasic:
    """Test basic register/lookup functionality."""

    def test_register_and_lookup(self):
        reg = TypeRegistry()
        reg.register_variable("MyVar", "int")
        assert reg.lookup("MyVar") == "int"

    def test_lookup_unknown_returns_none(self):
        reg = TypeRegistry()
        assert reg.lookup("UnknownVar") is None

    def test_resolve_type_falls_back_to_auto(self):
        reg = TypeRegistry()
        reg.register_variable("KnownVar", "float")
        assert reg.resolve_type("KnownVar") == "float"
        assert reg.resolve_type("UnknownVar") == "auto"

    def test_overwrite_registration(self):
        reg = TypeRegistry()
        reg.register_variable("Var", "int")
        reg.register_variable("Var", "float")
        assert reg.lookup("Var") == "float"


class TestTypeRegistryMetadata:
    """Test populate_from_metadata."""

    def test_populate_variables(self):
        reg = TypeRegistry()
        reg.populate_from_metadata({
            "variables": [
                {"name": "Health", "type": "FloatProperty"},
                {"name": "Name", "type": "StrProperty"},
                {"name": "IsValid", "type": "BoolProperty"},
            ]
        })
        assert reg.lookup("Health") == "float"
        assert reg.lookup("Name") == "FString"
        assert reg.lookup("IsValid") == "bool"

    def test_populate_function_params(self):
        reg = TypeRegistry()
        reg.populate_from_metadata({
            "functions": [
                {
                    "name": "TakeDamage",
                    "params": [
                        {"name": "Amount", "type": "FloatProperty"},
                        {"name": "OutResult", "type": "IntProperty", "flags": "OutParm"},
                    ],
                    "return_value": {"name": "Result", "type": "BoolProperty"},
                }
            ]
        })
        assert reg.lookup("Amount") == "float"
        assert reg.lookup("OutResult") == "int&"
        assert reg.lookup("Result") == "bool"

    def test_populate_unknown_type(self):
        reg = TypeRegistry()
        reg.populate_from_metadata({
            "variables": [{"name": "Custom", "type": "SomeCustomProperty"}]
        })
        assert reg.lookup("Custom") == "SomeCustomProperty"


class TestUeToCpp:
    """Test ue_to_cpp type mapping."""

    def test_basic_types(self):
        reg = TypeRegistry()
        assert reg.ue_to_cpp("IntProperty") == "int"
        assert reg.ue_to_cpp("FloatProperty") == "float"
        assert reg.ue_to_cpp("BoolProperty") == "bool"
        assert reg.ue_to_cpp("StrProperty") == "FString"
        assert reg.ue_to_cpp("NameProperty") == "FName"
        assert reg.ue_to_cpp("TextProperty") == "FText"
        assert reg.ue_to_cpp("ObjectProperty") == "UObject*"
        assert reg.ue_to_cpp("ArrayProperty") == "TArray"
        assert reg.ue_to_cpp("MapProperty") == "TMap"

    def test_unknown_type_passthrough(self):
        reg = TypeRegistry()
        assert reg.ue_to_cpp("UnknownProperty") == "UnknownProperty"
