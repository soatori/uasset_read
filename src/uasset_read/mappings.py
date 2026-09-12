"""Usmap mapping reader and unified type model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from uasset_read.archive import ByteArchive
from uasset_read.exceptions import ParseError
from uasset_read.memory_safety import ResourceBudget


MAX_RECURSION_DEPTH: int = 64

_PROPERTY_TYPE_NAMES = {
    0: "ByteProperty",
    1: "BoolProperty",
    2: "IntProperty",
    3: "FloatProperty",
    4: "ObjectProperty",
    5: "NameProperty",
    6: "DelegateProperty",
    7: "DoubleProperty",
    8: "ArrayProperty",
    9: "StructProperty",
    10: "StrProperty",
    11: "TextProperty",
    12: "InterfaceProperty",
    13: "MulticastDelegateProperty",
    14: "WeakObjectProperty",
    15: "LazyObjectProperty",
    16: "AssetObjectProperty",
    17: "SoftObjectProperty",
    18: "UInt64Property",
    19: "UInt32Property",
    20: "UInt16Property",
    21: "Int64Property",
    22: "Int16Property",
    23: "Int8Property",
    24: "MapProperty",
    25: "SetProperty",
    26: "EnumProperty",
    27: "FieldPathProperty",
    28: "OptionalProperty",
    29: "Utf8StrProperty",
    30: "AnsiStrProperty",
    31: "ClassProperty",
    32: "MulticastInlineDelegateProperty",
    33: "SoftClassProperty",
    34: "VerseStringProperty",
    35: "VerseDynamicProperty",
    36: "VerseFunctionProperty",
    0xFD: "CustomProperty_FD",
    0xFE: "CustomProperty_FE",
    0xFF: "Unknown",
}


@dataclass
class PropertyType:
    """Property type description from mapping file."""

    type: str
    struct_type: str | None = None
    inner_type: "PropertyType" | None = None
    value_type: "PropertyType" | None = None
    enum_name: str | None = None


@dataclass
class PropertyInfo:
    """Field description from mapping file."""

    index: int
    name: str
    mapping_type: PropertyType
    array_size: int = 1


@dataclass
class StructMapping:
    """Class/struct description from mapping file."""

    name: str
    super_type: str | None = None
    properties: dict[int, PropertyInfo] = field(default_factory=dict)
    property_count: int = 0

    def property_by_name(self, name: str) -> PropertyInfo | None:
        lowered = name.lower()
        for prop in self.properties.values():
            if prop.name.lower() == lowered:
                return prop
        return None


@dataclass
class TypeMappings:
    """Unified Usmap mapping container."""

    types: dict[str, StructMapping] = field(default_factory=dict)

    def get_struct(self, name: str | None) -> StructMapping | None:
        if not name:
            return None
        key = name.split(".")[-1]
        return self.types.get(key) or self.types.get(name)

    def property_by_name(self, struct_name: str | None, property_name: str) -> PropertyInfo | None:
        """Find a mapped property on a struct, walking mapped super structs."""
        seen: set[str] = set()
        current = self.get_struct(struct_name)
        while current is not None and current.name not in seen:
            seen.add(current.name)
            found = current.property_by_name(property_name)
            if found is not None:
                return found
            current = self.get_struct(current.super_type)
        return None


def _read_name(ar: ByteArchive, lut: list[str]) -> str | None:
    """Read a usmap name-table reference (i32 index; -1 means None)."""
    idx = ar.read_i32()
    if idx == -1:
        return None
    if idx < 0 or idx >= len(lut):
        raise ParseError(f"Usmap name index out of bounds: {idx}")
    return lut[idx]


class UsmapParser:
    """Read CUE4Parse-compatible .usmap mapping file."""

    FILE_MAGIC = 0x30C4

    def __init__(self, path_or_bytes: str | bytes, budget: ResourceBudget | None = None):
        if isinstance(path_or_bytes, bytes):
            data = path_or_bytes
        else:
            if budget is not None:
                file_size = Path(path_or_bytes).stat().st_size
                budget.reserve(file_size, "usmap_file_read")
            with open(path_or_bytes, "rb") as fh:
                data = fh.read()
        self.mappings = self._parse(data, budget)

    def _parse(self, data: bytes, budget: ResourceBudget | None = None) -> TypeMappings:
        reader = ByteArchive(data)
        magic = reader.read_u16()
        if magic != self.FILE_MAGIC:
            raise ParseError("Invalid Usmap magic")
        version = reader.read_u8()
        if version > 4:
            raise ParseError(f"Invalid Usmap version: {version}")

        if version >= 1 and reader.read_u8():
            reader.read(8)  # PackageFileVersion
            custom_count = reader.read_i32()
            if custom_count < 0:
                raise ParseError("Invalid Usmap CustomVersion count")
            reader.read(custom_count * 20)
            reader.read(4)  # NetCL

        compression = reader.read_u8()
        comp_size = reader.read_u32()
        decomp_size = reader.read_u32()
        payload = reader.read(comp_size)
        data = self._decompress(payload, compression, comp_size, decomp_size, budget=budget)
        ar = ByteArchive(data)

        name_count = ar.read_u32()
        name_lut: list[str] = []
        for _ in range(name_count):
            length = ar.read_u16() if version >= 2 else ar.read_u8()
            name_lut.append(ar.read(length).decode("utf-8", errors="replace"))

        mappings = TypeMappings()
        enum_count = ar.read_u32()
        for _ in range(enum_count):
            _read_name(ar, name_lut)
            value_count = ar.read_u16() if version >= 3 else ar.read_u8()
            for _ in range(value_count):
                if version >= 4:
                    ar.read_u64()
                _read_name(ar, name_lut)

        struct_count = ar.read_u32()
        for _ in range(struct_count):
            struct = self._parse_struct(ar, name_lut)
            mappings.types[struct.name] = struct
        return mappings

    def _decompress(
        self, payload: bytes, method: int, comp_size: int, decomp_size: int, budget: "ResourceBudget | None" = None
    ) -> bytes:
        if method == 0:
            if comp_size != decomp_size:
                raise ParseError(f"Usmap uncompressed size mismatch: {comp_size} != {decomp_size}")
            return payload
        if method == 2:
            try:
                import brotli  # type: ignore
            except ImportError as exc:
                raise ParseError("Usmap Brotli compression requires the brotli package") from exc
            if budget is not None:
                budget.reserve(decomp_size, "usmap_brotli_decompress")
            result = brotli.decompress(payload)
            if len(result) > decomp_size:
                raise ParseError(f"Usmap Brotli decompressed size exceeds expected: {len(result)} > {decomp_size}")
            return result
        if method == 3:
            try:
                import zstandard as zstd  # type: ignore
            except ImportError as exc:
                raise ParseError("Usmap ZStandard compression requires the zstandard package") from exc
            if budget is not None:
                budget.reserve(decomp_size, "usmap_zstd_decompress")
            return zstd.ZstdDecompressor().decompress(payload, max_output_size=decomp_size)
        raise ParseError(f"Unsupported Usmap compression method: {method}")

    def _parse_struct(self, ar: ByteArchive, lut: list[str]) -> StructMapping:
        name = _read_name(ar, lut) or ""
        super_type = _read_name(ar, lut)
        property_count = ar.read_u16()
        serializable_count = ar.read_u16()
        properties: dict[int, PropertyInfo] = {}
        for _ in range(serializable_count):
            prop = self._parse_property_info(ar, lut)
            for offset in range(prop.array_size):
                properties[prop.index + offset] = PropertyInfo(
                    index=prop.index + offset,
                    name=prop.name,
                    mapping_type=prop.mapping_type,
                    array_size=prop.array_size,
                )
        return StructMapping(name=name, super_type=super_type, properties=properties, property_count=property_count)

    def _parse_property_info(self, ar: ByteArchive, lut: list[str]) -> PropertyInfo:
        index = ar.read_u16()
        array_dim = ar.read_u8()
        name = _read_name(ar, lut) or ""
        return PropertyInfo(
            index=index, name=name, mapping_type=self._parse_property_type(ar, lut), array_size=array_dim
        )

    def _parse_property_type(self, ar: ByteArchive, lut: list[str], depth: int = 0) -> PropertyType:
        if depth > MAX_RECURSION_DEPTH:
            raise ParseError(f"Usmap property type recursion depth exceeds limit {MAX_RECURSION_DEPTH}")
        type_id = ar.read_u8()
        type_name = _PROPERTY_TYPE_NAMES.get(type_id, "Unknown")
        if type_name == "EnumProperty":
            inner = self._parse_property_type(ar, lut, depth + 1)
            return PropertyType(type_name, inner_type=inner, enum_name=_read_name(ar, lut))
        if type_name == "StructProperty":
            return PropertyType(type_name, struct_type=_read_name(ar, lut))
        if type_name in {"ArrayProperty", "SetProperty", "OptionalProperty"}:
            return PropertyType(type_name, inner_type=self._parse_property_type(ar, lut, depth + 1))
        if type_name == "MapProperty":
            return PropertyType(
                type_name,
                inner_type=self._parse_property_type(ar, lut, depth + 1),
                value_type=self._parse_property_type(ar, lut, depth + 1),
            )
        return PropertyType(type_name)


def load_usmap(path: str, budget: ResourceBudget | None = None) -> TypeMappings:
    """Load a .usmap mapping file into a TypeMappings container."""
    lower = path.lower()
    if lower.endswith(".usmap"):
        return UsmapParser(path, budget=budget).mappings
    raise ParseError(f"Unsupported mapping file type: {Path(path).name}")
