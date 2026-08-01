"""Native FField / FProperty deserialization for UFunction Script reading.

Each ``NativeFieldDeclaration`` retains raw package indices, resolved names,
and type-specific tail data.  The ``native_field_cpp_type`` mapper produces
concrete C++ type strings using the resolved names so callers never need the
archive for downstream type mapping.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from uasset_read.archive import ByteArchive
from uasset_read.kismet.value_types import FNameRef

if TYPE_CHECKING:
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Package flags constant (mirrored from constants.py to avoid circular import)
# ---------------------------------------------------------------------------
PKG_FilterEditorOnly = 0x80000000

# FReleaseObjectVersion threshold for replication condition byte
_PROPERTIES_SERIALIZE_REP_CONDITION_VERSION = 21


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@dataclass
class NativeFieldContext:
    """Resolution context for native field reading.

    Holds the name map, import/export maps, package flags, and release
    version needed to resolve package indices and determine which prefix
    fields are present.
    """

    name_map: list[str]
    import_map: list[ObjectImport]
    export_map: list[ObjectExport]
    package_flags: int = 0
    release_version: int = 21  # FReleaseObjectVersion


# ---------------------------------------------------------------------------
# Declaration
# ---------------------------------------------------------------------------

@dataclass
class NativeFieldDeclaration:
    """Deserialized native FField / FProperty record.

    Retains raw package indices for diagnostics and aligned resolved names
    for C++ type mapping.
    """

    type_name: str
    name: str = ""
    array_dim: int = 1
    element_size: int = 0
    property_flags: int = 0
    rep_notify_name: FNameRef | None = None
    replication_condition: int = 0
    metadata: dict[str, str] = field(default_factory=dict)
    # Raw package indices (preserved for diagnostics)
    references: list[int] = field(default_factory=list)
    # Resolved names parallel to references (None when index is null or out-of-range)
    reference_names: list[str | None] = field(default_factory=list)
    # Inner fields for container types (array/set/map/enum/optional) — added in Task 4
    inner_fields: list[NativeFieldDeclaration] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Name resolution
# ---------------------------------------------------------------------------

def _resolve_package_index(
    raw_index: int,
    context: NativeFieldContext,
) -> str | None:
    """Resolve a raw int32 package index to a name through the import/export maps.

    Index 0 is a legitimate null (returns None).
    Positive indices are export table entries (1-based).
    Negative indices are import table entries (-1-based).
    Out-of-range nonzero indices raise ValueError.
    """
    if raw_index == 0:
        return None
    if raw_index > 0:
        export_idx = raw_index - 1
        if export_idx >= len(context.export_map):
            raise ValueError(f"Out-of-range package index {raw_index}")
        return context.export_map[export_idx].object_name
    # raw_index < 0 → import
    import_idx = -raw_index - 1
    if import_idx >= len(context.import_map):
        raise ValueError(f"Out-of-range package index {raw_index}")
    return context.import_map[import_idx].object_name


def _read_fname_ref(archive: ByteArchive, context: NativeFieldContext) -> FNameRef:
    """Read an FName as (u32 index, u32 number) and resolve the base name."""
    index = archive.read_u32()
    number = archive.read_u32()
    if 0 <= index < len(context.name_map):
        base_name = context.name_map[index]
    else:
        base_name = None
    return FNameRef(name_index=index, number=number, base_name=base_name)


def _read_package_ref(archive: ByteArchive, context: NativeFieldContext) -> tuple[int, str | None]:
    """Read an int32 package index and resolve it to a name."""
    raw_index = archive.read_i32()
    name = _resolve_package_index(raw_index, context)
    return raw_index, name


# ---------------------------------------------------------------------------
# FProperty base prefix
# ---------------------------------------------------------------------------

def _read_fproperty_prefix(
    archive: ByteArchive,
    context: NativeFieldContext,
) -> tuple[str, FNameRef, int, int, int, int, FNameRef | None, int]:
    """Read the common FProperty prefix after the FField type-name.

    Returns:
        (name, name_ref, array_dim, element_size, property_flags,
         rep_index, rep_notify_name, replication_condition)
    """
    # NamePrivate: FName
    name_ref = _read_fname_ref(archive, context)

    # FlagsPrivate: u32 (absent when PKG_FilterEditorOnly)
    if not (context.package_flags & PKG_FilterEditorOnly):
        _flags = archive.read_u32()

    # ArrayDim: u16
    array_dim = archive.read_u16()
    # ElementSize: u16
    element_size = archive.read_u16()
    # PropertyFlags: u64
    property_flags = archive.read_u64()
    # RepIndex: u16
    rep_index = archive.read_u16()
    # RepNotifyFunc: FName
    rep_notify_name = _read_fname_ref(archive, context)

    # ReplicationCondition: u8 (Release version >= 21)
    replication_condition = 0
    if context.release_version >= _PROPERTIES_SERIALIZE_REP_CONDITION_VERSION:
        replication_condition = archive.read_u8()

    return (
        name_ref.base_name or "",
        name_ref,
        array_dim,
        element_size,
        property_flags,
        rep_index,
        rep_notify_name,
        replication_condition,
    )


# ---------------------------------------------------------------------------
# Metadata reading (uncooked)
# ---------------------------------------------------------------------------

def _read_metadata(archive: ByteArchive, context: NativeFieldContext) -> dict[str, str]:
    """Read the metadata boolean and, when true, a TMap<FName, FString>.

    Returns a dict of key-value pairs.  For cooked packages or when the
    metadata flag is false, returns an empty dict.
    """
    if context.package_flags & PKG_FilterEditorOnly:
        return {}

    has_metadata = archive.read_u8() != 0
    if not has_metadata:
        return {}

    count = archive.read_i32()
    if count < 0:
        raise ValueError(f"Negative metadata count: {count}")

    metadata: dict[str, str] = {}
    for _ in range(count):
        key_ref = _read_fname_ref(archive, context)
        value = archive.read_fstring()
        key_name = key_ref.base_name or ""
        metadata[key_name] = value
    return metadata


# ---------------------------------------------------------------------------
# Leaf type-specific tail readers
# ---------------------------------------------------------------------------

def _read_bool_tail(archive: ByteArchive) -> None:
    """BoolProperty: six uint8 values."""
    for _ in range(6):
        archive.read_u8()


def _read_byte_tail(
    archive: ByteArchive,
    context: NativeFieldContext,
    decl: NativeFieldDeclaration,
) -> None:
    """ByteProperty: one int32 UObject reference (enum class).

    Null reference (index 0) maps to uint8.
    """
    raw, name = _read_package_ref(archive, context)
    decl.references.append(raw)
    decl.reference_names.append(name)


def _read_object_tail(
    archive: ByteArchive,
    context: NativeFieldContext,
    decl: NativeFieldDeclaration,
) -> None:
    """Object/WeakObject/LazyObject/SoftObjectProperty: one int32 class reference."""
    raw, name = _read_package_ref(archive, context)
    decl.references.append(raw)
    decl.reference_names.append(name)


def _read_class_tail(
    archive: ByteArchive,
    context: NativeFieldContext,
    decl: NativeFieldDeclaration,
) -> None:
    """Class/SoftClassProperty: base class ref + meta-class ref."""
    raw1, name1 = _read_package_ref(archive, context)
    decl.references.append(raw1)
    decl.reference_names.append(name1)
    raw2, name2 = _read_package_ref(archive, context)
    decl.references.append(raw2)
    decl.reference_names.append(name2)


def _read_interface_tail(
    archive: ByteArchive,
    context: NativeFieldContext,
    decl: NativeFieldDeclaration,
) -> None:
    """InterfaceProperty: one int32 interface-class reference."""
    raw, name = _read_package_ref(archive, context)
    decl.references.append(raw)
    decl.reference_names.append(name)


def _read_struct_tail(
    archive: ByteArchive,
    context: NativeFieldContext,
    decl: NativeFieldDeclaration,
) -> None:
    """StructProperty: one int32 struct reference."""
    raw, name = _read_package_ref(archive, context)
    decl.references.append(raw)
    decl.reference_names.append(name)


def _read_delegate_tail(
    archive: ByteArchive,
    context: NativeFieldContext,
    decl: NativeFieldDeclaration,
) -> None:
    """Delegate / MulticastDelegate variants: one int32 signature-function ref."""
    raw, name = _read_package_ref(archive, context)
    decl.references.append(raw)
    decl.reference_names.append(name)


def _read_fieldpath_tail(
    archive: ByteArchive,
    context: NativeFieldContext,
    decl: NativeFieldDeclaration,
) -> None:
    """FieldPathProperty: one serialized FName field-class name."""
    fname_ref = _read_fname_ref(archive, context)
    # Store as a reference using the name index as a pseudo-package-index
    decl.references.append(fname_ref.name_index)
    decl.reference_names.append(fname_ref.base_name)


# Scalar types with no extra bytes
_NO_EXTRA_BYTES_TYPES = frozenset({
    "Int8Property", "Int16Property", "IntProperty", "Int64Property",
    "UInt16Property", "UInt32Property", "UInt64Property",
    "FloatProperty", "DoubleProperty",
    "NameProperty", "StrProperty", "TextProperty",
})


# ---------------------------------------------------------------------------
# Main reading API
# ---------------------------------------------------------------------------

def _read_single_field(
    archive: ByteArchive,
    context: NativeFieldContext,
) -> NativeFieldDeclaration:
    """Read a single native FField from the archive.

    The archive must be positioned at the start of the field (type-name FName).
    """
    # FField::Serialize writes the type name as an FName
    type_ref = _read_fname_ref(archive, context)
    type_name = type_ref.base_name or ""

    # Build the declaration
    decl = NativeFieldDeclaration(type_name=type_name)

    # Read the common FProperty prefix
    (
        name, _name_ref, array_dim, element_size,
        property_flags, _rep_index, rep_notify_name, replication_condition,
    ) = _read_fproperty_prefix(archive, context)

    decl.name = name
    decl.array_dim = array_dim
    decl.element_size = element_size
    decl.property_flags = property_flags
    decl.rep_notify_name = rep_notify_name
    decl.replication_condition = replication_condition

    # Metadata (uncooked)
    decl.metadata = _read_metadata(archive, context)

    # Type-specific tail
    if type_name in _NO_EXTRA_BYTES_TYPES:
        pass  # no extra bytes
    elif type_name == "BoolProperty":
        _read_bool_tail(archive)
    elif type_name == "ByteProperty":
        _read_byte_tail(archive, context, decl)
    elif type_name in ("ObjectProperty", "WeakObjectProperty", "LazyObjectProperty", "SoftObjectProperty"):
        _read_object_tail(archive, context, decl)
    elif type_name in ("ClassProperty", "SoftClassProperty"):
        _read_class_tail(archive, context, decl)
    elif type_name == "InterfaceProperty":
        _read_interface_tail(archive, context, decl)
    elif type_name == "StructProperty":
        _read_struct_tail(archive, context, decl)
    elif type_name in (
        "DelegateProperty",
        "MulticastDelegateProperty",
        "MulticastSparseDelegateProperty",
        "InlineMulticastDelegateProperty",
    ):
        _read_delegate_tail(archive, context, decl)
    elif type_name == "FieldPathProperty":
        _read_fieldpath_tail(archive, context, decl)
    else:
        # Unknown property class — emit unsupported_native_field failure
        logger.warning(
            "Unsupported native field type: %s at offset %d",
            type_name, archive.tell(),
        )
        decl.type_name = f"unsupported:{type_name}"

    return decl


def read_native_fields(
    archive: ByteArchive,
    count: int,
    context: NativeFieldContext,
) -> list[NativeFieldDeclaration]:
    """Read ``count`` consecutive native FProperty declarations.

    The archive must be positioned at the first field's type-name FName.
    Returns a list of deserialized declarations.
    """
    declarations: list[NativeFieldDeclaration] = []
    for _ in range(count):
        declarations.append(_read_single_field(archive, context))
    return declarations


# ---------------------------------------------------------------------------
# C++ type mapping
# ---------------------------------------------------------------------------

# Scalar type name → C++ type
_SCALAR_CPP_TYPES: dict[str, str] = {
    "Int8Property": "int8",
    "Int16Property": "int16",
    "IntProperty": "int32",
    "Int64Property": "int64",
    "UInt16Property": "uint16",
    "UInt32Property": "uint32",
    "UInt64Property": "uint64",
    "FloatProperty": "float",
    "DoubleProperty": "double",
    "BoolProperty": "bool",
    "NameProperty": "FName",
    "StrProperty": "FString",
    "TextProperty": "FText",
    "ObjectProperty": "UObject*",
    "WeakObjectProperty": "TWeakObjectPtr<UObject>",
    "LazyObjectProperty": "TLazyObjectPtr<UObject>",
    "SoftObjectProperty": "TSoftObjectPtr<UObject>",
    "ClassProperty": "UClass*",
    "SoftClassProperty": "TSoftClassPtr<UObject>",
    "InterfaceProperty": "TScriptInterface<IInterface>",
    "StructProperty": "FStruct",
    "ByteProperty": "uint8",
    "DelegateProperty": "FScriptDelegate",
    "MulticastDelegateProperty": "FMulticastScriptDelegate",
    "MulticastSparseDelegateProperty": "FMulticastScriptDelegate",
    "InlineMulticastDelegateProperty": "FMulticastScriptDelegate",
    "FieldPathProperty": "FProperty*",
}


def native_field_cpp_type(field: NativeFieldDeclaration) -> str:
    """Map a NativeFieldDeclaration to its concrete C++ type string.

    Uses resolved reference_names so that object, struct, enum, and
    interface types are concrete without needing archive context later.
    """
    type_name = field.type_name

    # Unknown / unsupported types
    if type_name.startswith("unsupported:"):
        return f"/* {type_name} */"

    # ByteProperty with null enum → uint8, with enum → EEnumName
    if type_name == "ByteProperty":
        if field.references and field.references[0] == 0:
            return "uint8"
        enum_name = field.reference_names[0] if field.reference_names else None
        return enum_name or "uint8"

    # ObjectProperty uses the resolved class name
    if type_name == "ObjectProperty":
        class_name = field.reference_names[0] if field.reference_names else None
        if class_name:
            return f"{class_name}*"
        return "UObject*"

    # ClassProperty uses the base class name
    if type_name in ("ClassProperty", "SoftClassProperty"):
        class_name = field.reference_names[0] if field.reference_names else None
        if class_name:
            return f"TSoftClassPtr<{class_name}>" if type_name == "SoftClassProperty" else f"{class_name}*"
        return "UClass*" if type_name == "ClassProperty" else "TSoftClassPtr<UObject>"

    # InterfaceProperty uses the interface name
    if type_name == "InterfaceProperty":
        iface_name = field.reference_names[0] if field.reference_names else None
        if iface_name:
            return f"TScriptInterface<{iface_name}>"
        return "TScriptInterface<IInterface>"

    # StructProperty uses the resolved struct name
    if type_name == "StructProperty":
        struct_name = field.reference_names[0] if field.reference_names else None
        if struct_name:
            return struct_name
        return "FStruct"

    # DelegateProperty uses the resolved signature function name
    if type_name == "DelegateProperty":
        sig_name = field.reference_names[0] if field.reference_names else None
        if sig_name:
            return f"FScriptDelegate /* {sig_name} */"
        return "FScriptDelegate"

    # Multicast delegates use resolved signature
    if type_name in ("MulticastDelegateProperty", "MulticastSparseDelegateProperty", "InlineMulticastDelegateProperty"):
        sig_name = field.reference_names[0] if field.reference_names else None
        if sig_name:
            return f"FMulticastScriptDelegate /* {sig_name} */"
        return "FMulticastScriptDelegate"

    # Scalar types
    if type_name in _SCALAR_CPP_TYPES:
        return _SCALAR_CPP_TYPES[type_name]

    # FieldPathProperty
    if type_name == "FieldPathProperty":
        field_class = field.reference_names[0] if field.reference_names else None
        if field_class:
            return f"FProperty* /* {field_class} */"
        return "FProperty*"

    # Fallback
    return f"/* unknown: {type_name} */"
