"""Usmap/Jmap 映射读取与统一类型模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
import gzip
import json
import os
import struct
from typing import Dict, Optional, Any

from uasset_read.exceptions import ParseError


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
    """映射文件中的属性类型描述。"""
    type: str
    struct_type: Optional[str] = None
    inner_type: Optional["PropertyType"] = None
    value_type: Optional["PropertyType"] = None
    enum_name: Optional[str] = None
    is_enum_as_byte: Optional[bool] = None


@dataclass
class PropertyInfo:
    """映射文件中的字段描述。"""
    index: int
    name: str
    mapping_type: PropertyType
    array_size: int = 1


@dataclass
class StructMapping:
    """映射文件中的类/结构体描述。"""
    name: str
    super_type: Optional[str] = None
    properties: Dict[int, PropertyInfo] = field(default_factory=dict)
    property_count: int = 0

    def property_by_name(self, name: str) -> Optional[PropertyInfo]:
        lowered = name.lower()
        for prop in self.properties.values():
            if prop.name.lower() == lowered:
                return prop
        return None


@dataclass
class TypeMappings:
    """统一的 Usmap/Jmap 映射容器。"""
    types: Dict[str, StructMapping] = field(default_factory=dict)
    enums: Dict[str, Dict[int, str]] = field(default_factory=dict)

    def get_struct(self, name: Optional[str]) -> Optional[StructMapping]:
        if not name:
            return None
        key = name.split(".")[-1]
        return self.types.get(key) or self.types.get(name)

    def property_by_name(self, struct_name: Optional[str], property_name: str) -> Optional[PropertyInfo]:
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


class _BytesReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read(self, size: int) -> bytes:
        if self.pos + size > len(self.data):
            raise ParseError("映射文件数据不足")
        value = self.data[self.pos:self.pos + size]
        self.pos += size
        return value

    def u8(self) -> int:
        return self.read(1)[0]

    def u16(self) -> int:
        return struct.unpack_from("<H", self.read(2))[0]

    def u32(self) -> int:
        return struct.unpack_from("<I", self.read(4))[0]

    def i32(self) -> int:
        return struct.unpack_from("<i", self.read(4))[0]

    def u64(self) -> int:
        return struct.unpack_from("<Q", self.read(8))[0]

    def name(self, lut: list[str]) -> Optional[str]:
        idx = self.i32()
        if idx == -1:
            return None
        if idx < 0 or idx >= len(lut):
            raise ParseError(f"Usmap 名称索引越界: {idx}")
        return lut[idx]


class UsmapParser:
    """读取 CUE4Parse 兼容的 .usmap 映射文件。"""
    FILE_MAGIC = 0x30C4

    def __init__(self, path_or_bytes: str | bytes):
        data = path_or_bytes if isinstance(path_or_bytes, bytes) else open(path_or_bytes, "rb").read()
        self.mappings = self._parse(data)

    def _parse(self, data: bytes) -> TypeMappings:
        reader = _BytesReader(data)
        magic = reader.u16()
        if magic != self.FILE_MAGIC:
            raise ParseError("Usmap magic 无效")
        version = reader.u8()
        if version > 4:
            raise ParseError(f"Usmap 版本无效: {version}")

        if version >= 1 and reader.u8():
            reader.read(8)  # PackageFileVersion
            custom_count = reader.i32()
            if custom_count < 0:
                raise ParseError("Usmap CustomVersion 数量无效")
            reader.read(custom_count * 20)
            reader.read(4)  # NetCL

        compression = reader.u8()
        comp_size = reader.u32()
        decomp_size = reader.u32()
        payload = reader.read(comp_size)
        data = self._decompress(payload, compression, comp_size, decomp_size)
        ar = _BytesReader(data)

        name_count = ar.u32()
        name_lut: list[str] = []
        for _ in range(name_count):
            length = ar.u16() if version >= 2 else ar.u8()
            name_lut.append(ar.read(length).decode("utf-8", errors="replace"))

        mappings = TypeMappings()
        enum_count = ar.u32()
        for _ in range(enum_count):
            enum_name = ar.name(name_lut) or ""
            value_count = ar.u16() if version >= 3 else ar.u8()
            values: Dict[int, str] = {}
            for index in range(value_count):
                if version >= 4:
                    value = int(ar.u64())
                    name = ar.name(name_lut) or ""
                else:
                    value = index
                    name = ar.name(name_lut) or ""
                values[value] = name
            mappings.enums.setdefault(enum_name, values)

        struct_count = ar.u32()
        for _ in range(struct_count):
            struct = self._parse_struct(ar, name_lut)
            mappings.types[struct.name] = struct
        return mappings

    def _decompress(self, payload: bytes, method: int, comp_size: int, decomp_size: int) -> bytes:
        if method == 0:
            if comp_size != decomp_size:
                raise ParseError("Usmap 未压缩数据大小不一致")
            return payload
        if method == 2:
            import brotli  # type: ignore
            return brotli.decompress(payload)
        if method == 3:
            try:
                import zstandard as zstd  # type: ignore
            except ImportError as exc:
                raise ParseError("Usmap ZStandard 压缩需要可用的 zstandard 后端") from exc
            return zstd.ZstdDecompressor().decompress(payload, max_output_size=decomp_size)
        raise ParseError(f"不支持的 Usmap 压缩方式: {method}")

    def _parse_struct(self, ar: _BytesReader, lut: list[str]) -> StructMapping:
        name = ar.name(lut) or ""
        super_type = ar.name(lut)
        property_count = ar.u16()
        serializable_count = ar.u16()
        properties: Dict[int, PropertyInfo] = {}
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

    def _parse_property_info(self, ar: _BytesReader, lut: list[str]) -> PropertyInfo:
        index = ar.u16()
        array_dim = ar.u8()
        name = ar.name(lut) or ""
        return PropertyInfo(index=index, name=name, mapping_type=self._parse_property_type(ar, lut), array_size=array_dim)

    def _parse_property_type(self, ar: _BytesReader, lut: list[str]) -> PropertyType:
        type_id = ar.u8()
        type_name = _PROPERTY_TYPE_NAMES.get(type_id, "Unknown")
        if type_name == "EnumProperty":
            inner = self._parse_property_type(ar, lut)
            return PropertyType(type_name, inner_type=inner, enum_name=ar.name(lut))
        if type_name == "StructProperty":
            return PropertyType(type_name, struct_type=ar.name(lut))
        if type_name in {"ArrayProperty", "SetProperty", "OptionalProperty"}:
            return PropertyType(type_name, inner_type=self._parse_property_type(ar, lut))
        if type_name == "MapProperty":
            return PropertyType(type_name, inner_type=self._parse_property_type(ar, lut), value_type=self._parse_property_type(ar, lut))
        return PropertyType(type_name)


class JmapParser:
    """读取 CUE4Parse 兼容的 .jmap/.jmap.gz 映射文件。"""

    def __init__(self, path_or_bytes: str | bytes):
        if isinstance(path_or_bytes, bytes):
            data = path_or_bytes
        else:
            data = open(path_or_bytes, "rb").read()
            if path_or_bytes.lower().endswith(".gz"):
                data = gzip.decompress(data)
        self.mappings = self._parse(json.loads(data.decode("utf-8")))

    def _parse(self, root: Dict[str, Any]) -> TypeMappings:
        mappings = TypeMappings()
        for full_name, obj in root.get("objects", {}).items():
            if not isinstance(obj, dict):
                continue
            short_name = full_name.split(".")[-1]
            obj_type = obj.get("type")
            if obj_type == "Enum":
                values: Dict[int, str] = {}
                for item in obj.get("names", []):
                    if isinstance(item, list) and len(item) >= 2:
                        values[int(item[1])] = str(item[0])
                mappings.enums[short_name] = values
            elif obj_type in {"Class", "ScriptStruct"}:
                properties: Dict[int, PropertyInfo] = {}
                index = 0
                for prop in obj.get("properties", []):
                    if not isinstance(prop, dict):
                        continue
                    info = self._parse_property_info(prop, index)
                    for offset in range(info.array_size):
                        properties[index] = PropertyInfo(index, info.name, info.mapping_type, info.array_size)
                        index += 1
                mappings.types[short_name] = StructMapping(
                    name=short_name,
                    super_type=(obj.get("super_struct") or "").split(".")[-1] or None,
                    properties=properties,
                    property_count=len(properties),
                )
        return mappings

    def _parse_property_info(self, prop: Dict[str, Any], index: int) -> PropertyInfo:
        return PropertyInfo(
            index=index,
            name=str(prop.get("name") or ""),
            mapping_type=self._parse_property_type(prop),
            array_size=int(prop.get("array_dim") or 1),
        )

    def _parse_property_type(self, prop: Dict[str, Any]) -> PropertyType:
        type_name = str(prop.get("type") or "Unknown")
        inner_src = prop.get("container") or prop.get("inner") or prop.get("key_prop")
        value_src = prop.get("value_prop")
        inner = self._parse_property_type(inner_src) if isinstance(inner_src, dict) else None
        value = self._parse_property_type(value_src) if isinstance(value_src, dict) else None
        if type_name == "EnumProperty" and inner is None:
            inner = PropertyType("ByteProperty")
        if type_name in {"ArrayProperty", "SetProperty", "OptionalProperty"} and inner is None:
            inner = PropertyType("Unknown")
        if type_name == "MapProperty":
            inner = inner or PropertyType("Unknown")
            value = value or PropertyType("Unknown")
        return PropertyType(
            type=type_name,
            struct_type=(prop.get("struct") or "").split(".")[-1] or None,
            inner_type=inner,
            value_type=value,
            enum_name=(prop.get("enum") or "").split(".")[-1] or None,
        )


class TypeMappingsProvider:
    """按扩展名加载 Usmap/Jmap 映射。"""

    def __init__(self, mappings: TypeMappings):
        self.mappings = mappings

    @classmethod
    def from_file(cls, path: str) -> "TypeMappingsProvider":
        lower = path.lower()
        if lower.endswith(".usmap"):
            return cls(UsmapParser(path).mappings)
        if lower.endswith(".jmap") or lower.endswith(".jmap.gz"):
            return cls(JmapParser(path).mappings)
        raise ParseError(f"不支持的映射文件类型: {os.path.basename(path)}")
