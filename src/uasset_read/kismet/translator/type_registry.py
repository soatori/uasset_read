"""TypeRegistry — UE → C++ type mapping for Kismet pseudocode generation."""
from __future__ import annotations


# UE Property type → C++ type mapping (aligned with GetPropertyType)
_UE_TO_CPP_TYPES: dict[str, str] = {
    "IntProperty": "int",
    "Int8Property": "int8",
    "Int16Property": "int16",
    "Int64Property": "int64",
    "UInt8Property": "uint8",
    "UInt16Property": "uint16",
    "UInt32Property": "uint32",
    "UInt64Property": "uint64",
    "FloatProperty": "float",
    "DoubleProperty": "double",
    "BoolProperty": "bool",
    "ByteProperty": "uint8",
    "StrProperty": "FString",
    "VerseStringProperty": "FString",
    "NameProperty": "FName",
    "TextProperty": "FText",
    "ObjectProperty": "UObject*",
    "ClassProperty": "UClass*",
    "StructProperty": "FStruct",
    "InterfaceProperty": "IInterface",
    "ArrayProperty": "TArray",
    "MapProperty": "TMap",
    "SetProperty": "TSet",
    "EnumProperty": "Enum",
    "DelegateProperty": "FScriptDelegate",
    "MulticastDelegateProperty": "FMulticastScriptDelegate",
    "SoftObjectProperty": "FSoftObjectPath",
    "SoftClassProperty": "FSoftClassPath",
    "WeakObjectProperty": "TWeakObjectPtr",
    "FieldPathProperty": "FFieldPath",
    "OptionalProperty": "TOptional",
}


class TypeRegistry:
    """
    Variable type registry for C++ pseudocode generation.

    Priority: explicitly registered type → metadata-inferred type → `auto`.
    """

    def __init__(self) -> None:
        self._types: dict[str, str] = {}

    def register_variable(self, name: str, cpp_type: str) -> None:
        """Register a variable with an explicit C++ type."""
        self._types[name] = cpp_type

    def lookup(self, name: str) -> str | None:
        """Look up the C++ type for a variable. Returns None if not found."""
        return self._types.get(name)


# Export module-level constant
UE_TYPE_MAP = _UE_TO_CPP_TYPES
