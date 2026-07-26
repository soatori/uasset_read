"""mappings 模块单元测试 — UsmapParser / JmapParser。

覆盖范围：
- mappings.py: UsmapParser、JmapParser、TypeMappings、StructMapping、
  PropertyInfo、PropertyType、_PROPERTY_TYPE_NAMES、TypeMappingsProvider
"""
from __future__ import annotations

import gzip
import json
import struct

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.mappings import (
    JmapParser,
    PropertyInfo,
    PropertyType,
    StructMapping,
    TypeMappings,
    TypeMappingsProvider,
    UsmapParser,
    _PROPERTY_TYPE_NAMES,
)


# ============================================================================
# _PROPERTY_TYPE_NAMES
# ============================================================================


class TestPropertyTypeNames:
    """_PROPERTY_TYPE_NAMES 应包含所有基本属性类型。"""

    def test_basic_types(self):
        assert _PROPERTY_TYPE_NAMES[0] == "ByteProperty"
        assert _PROPERTY_TYPE_NAMES[1] == "BoolProperty"
        assert _PROPERTY_TYPE_NAMES[2] == "IntProperty"
        assert _PROPERTY_TYPE_NAMES[3] == "FloatProperty"
        assert _PROPERTY_TYPE_NAMES[4] == "ObjectProperty"

    def test_struct_property(self):
        assert _PROPERTY_TYPE_NAMES[9] == "StructProperty"

    def test_array_property(self):
        assert _PROPERTY_TYPE_NAMES[8] == "ArrayProperty"

    def test_map_property(self):
        assert _PROPERTY_TYPE_NAMES[24] == "MapProperty"

    def test_unknown(self):
        assert _PROPERTY_TYPE_NAMES[0xFF] == "Unknown"

    def test_custom_property_types(self):
        assert _PROPERTY_TYPE_NAMES[0xFD] == "CustomProperty_FD"
        assert _PROPERTY_TYPE_NAMES[0xFE] == "CustomProperty_FE"


# ============================================================================
# PropertyType — 数据类
# ============================================================================


class TestPropertyType:
    """PropertyType 应正确创建。"""

    def test_simple_type(self):
        pt = PropertyType(type="IntProperty")
        assert pt.type == "IntProperty"
        assert pt.struct_type is None
        assert pt.inner_type is None

    def test_struct_type(self):
        pt = PropertyType(type="StructProperty", struct_type="Vector")
        assert pt.struct_type == "Vector"

    def test_nested_type(self):
        inner = PropertyType(type="IntProperty")
        outer = PropertyType(type="ArrayProperty", inner_type=inner)
        assert outer.inner_type is inner


# ============================================================================
# PropertyInfo — 数据类
# ============================================================================


class TestPropertyInfo:
    """PropertyInfo 应正确创建。"""

    def test_basic_info(self):
        pi = PropertyInfo(
            index=0,
            name="Health",
            mapping_type=PropertyType(type="FloatProperty"),
        )
        assert pi.index == 0
        assert pi.name == "Health"
        assert pi.array_size == 1


# ============================================================================
# StructMapping — 数据类
# ============================================================================


class TestStructMapping:
    """StructMapping 应正确创建和查询。"""

    def test_basic_mapping(self):
        sm = StructMapping(name="TestStruct", super_type=None)
        assert sm.name == "TestStruct"
        assert sm.properties == {}
        assert sm.property_count == 0

    def test_property_by_name_found(self):
        pi = PropertyInfo(index=0, name="Health", mapping_type=PropertyType(type="FloatProperty"))
        sm = StructMapping(name="Test", properties={0: pi})
        result = sm.property_by_name("Health")
        assert result is pi

    def test_property_by_name_case_insensitive(self):
        pi = PropertyInfo(index=0, name="Health", mapping_type=PropertyType(type="FloatProperty"))
        sm = StructMapping(name="Test", properties={0: pi})
        result = sm.property_by_name("health")
        assert result is pi

    def test_property_by_name_not_found(self):
        sm = StructMapping(name="Test")
        assert sm.property_by_name("Nonexistent") is None


# ============================================================================
# TypeMappings — 数据类
# ============================================================================


class TestTypeMappings:
    """TypeMappings 应正确创建和查询。"""

    def test_get_struct_found(self):
        sm = StructMapping(name="Vector")
        tm = TypeMappings(types={"Vector": sm})
        assert tm.get_struct("Vector") is sm

    def test_get_struct_with_dot_prefix(self):
        sm = StructMapping(name="Vector")
        tm = TypeMappings(types={"Vector": sm})
        assert tm.get_struct("Engine.Vector") is sm

    def test_get_struct_not_found(self):
        tm = TypeMappings()
        assert tm.get_struct("Unknown") is None

    def test_get_struct_none_name(self):
        tm = TypeMappings()
        assert tm.get_struct(None) is None

    def test_property_by_name_found(self):
        pi = PropertyInfo(index=0, name="X", mapping_type=PropertyType(type="FloatProperty"))
        sm = StructMapping(name="Vector", properties={0: pi})
        tm = TypeMappings(types={"Vector": sm})
        result = tm.property_by_name("Vector", "X")
        assert result is pi

    def test_property_by_name_walks_super(self):
        pi_parent = PropertyInfo(index=0, name="ParentProp", mapping_type=PropertyType(type="IntProperty"))
        parent = StructMapping(name="Parent", properties={0: pi_parent})
        child = StructMapping(name="Child", super_type="Parent")
        tm = TypeMappings(types={"Parent": parent, "Child": child})
        result = tm.property_by_name("Child", "ParentProp")
        assert result is pi_parent

    def test_property_by_name_not_found(self):
        tm = TypeMappings()
        assert tm.property_by_name("Unknown", "prop") is None


# ============================================================================
# UsmapParser — 合成 .usmap 文件解析
# ============================================================================


def _build_usmap_v0(
    name_table: list[str] | None = None,
    enums: dict[str, dict[int, str]] | None = None,
    schemas: list[dict] | None = None,
) -> bytes:
    """构造合成的 v0 .usmap 二进制数据。

    v0 格式:
        magic(u16) + version(u8) + compression(u8) + comp_size(u32) + decomp_size(u32)
        Payload:
            NameTable: count(u32) + names[length(u8 for v0) + bytes]
            EnumTable: count(u32) + enums[...]
            SchemaTable: count(u32) + schemas[...]
    """
    if name_table is None:
        name_table = []
    if enums is None:
        enums = {}
    if schemas is None:
        schemas = []

    payload = bytearray()

    # NameTable — v0 使用 u8 长度
    payload += struct.pack("<I", len(name_table))
    for name in name_table:
        encoded = name.encode("utf-8")
        payload += struct.pack("<B", len(encoded))  # u8 for v0
        payload += encoded

    # EnumTable
    payload += struct.pack("<I", len(enums))
    for enum_name, values in enums.items():
        name_idx = name_table.index(enum_name) if enum_name in name_table else 0
        payload += struct.pack("<i", name_idx)
        # value count — v0 使用 u8
        payload += struct.pack("<B", len(values))
        for val_int, val_name in sorted(values.items()):
            val_name_idx = name_table.index(val_name) if val_name in name_table else 0
            payload += struct.pack("<i", val_name_idx)

    # SchemaTable
    payload += struct.pack("<I", len(schemas))
    for schema in schemas:
        name_idx = name_table.index(schema["name"]) if schema["name"] in name_table else 0
        payload += struct.pack("<i", name_idx)
        super_name = schema.get("super_type")
        if super_name and super_name in name_table:
            payload += struct.pack("<i", name_table.index(super_name))
        else:
            payload += struct.pack("<i", -1)
        props = schema.get("properties", [])
        payload += struct.pack("<H", len(props))
        payload += struct.pack("<H", len(props))
        for prop in props:
            payload += struct.pack("<H", prop.get("index", 0))
            payload += struct.pack("<B", prop.get("array_dim", 1))
            prop_name_idx = name_table.index(prop["name"]) if prop["name"] in name_table else 0
            payload += struct.pack("<i", prop_name_idx)
            type_id = prop.get("type_id", 2)  # default IntProperty
            payload += struct.pack("<B", type_id)
            if type_id == 9:  # StructProperty
                st_name = prop.get("struct_type", "")
                st_idx = name_table.index(st_name) if st_name in name_table else 0
                payload += struct.pack("<i", st_idx)

    payload = bytes(payload)
    header = struct.pack("<HBB II", 0x30C4, 0, 0, len(payload), len(payload))
    return header + payload


class TestUsmapParser:
    """UsmapParser 应正确解析 .usmap 文件。"""

    def test_parse_empty_usmap(self):
        data = _build_usmap_v0()
        parser = UsmapParser(data)
        assert parser.mappings.types == {}
        assert parser.mappings.enums == {}

    def test_parse_with_names(self):
        data = _build_usmap_v0(name_table=["foo", "bar"])
        parser = UsmapParser(data)
        assert "foo" in parser.mappings.types or len(parser.mappings.types) == 0

    def test_parse_with_enum(self):
        data = _build_usmap_v0(
            name_table=["Color", "Red", "Blue"],
            enums={"Color": {0: "Red", 1: "Blue"}},
        )
        parser = UsmapParser(data)
        assert "Color" in parser.mappings.enums
        assert parser.mappings.enums["Color"][0] == "Red"

    def test_parse_with_schema(self):
        data = _build_usmap_v0(
            name_table=["MyStruct", "Health"],
            schemas=[
                {
                    "name": "MyStruct",
                    "super_type": None,
                    "properties": [
                        {"index": 0, "name": "Health", "type_id": 3},  # FloatProperty
                    ],
                }
            ],
        )
        parser = UsmapParser(data)
        assert "MyStruct" in parser.mappings.types
        sm = parser.mappings.types["MyStruct"]
        assert sm.name == "MyStruct"
        assert len(sm.properties) == 1

    def test_invalid_magic_raises(self):
        data = struct.pack("<H", 0x1234) + b"\x00" * 20
        with pytest.raises(ParseError, match="magic"):
            UsmapParser(data)

    def test_invalid_version_raises(self):
        data = struct.pack("<HBB II", 0x30C4, 99, 0, 0, 0)
        with pytest.raises(ParseError, match="version"):
            UsmapParser(data)


# ============================================================================
# JmapParser — 合成 JSON 映射文件解析
# ============================================================================


class TestJmapParser:
    """JmapParser 应正确解析 JSON 映射文件。"""

    def test_parse_empty_jmap(self):
        data = json.dumps({"objects": {}}).encode("utf-8")
        parser = JmapParser(data)
        assert parser.mappings.types == {}
        assert parser.mappings.enums == {}

    def test_parse_enum(self):
        root = {
            "objects": {
                "Color": {
                    "type": "Enum",
                    "names": [["Red", 0], ["Blue", 1]],
                }
            }
        }
        data = json.dumps(root).encode("utf-8")
        parser = JmapParser(data)
        assert "Color" in parser.mappings.enums
        assert parser.mappings.enums["Color"][0] == "Red"
        assert parser.mappings.enums["Color"][1] == "Blue"

    def test_parse_class(self):
        root = {
            "objects": {
                "MyClass": {
                    "type": "Class",
                    "super_struct": "SomeParent",
                    "properties": [
                        {"name": "Health", "type": "FloatProperty"},
                    ],
                }
            }
        }
        data = json.dumps(root).encode("utf-8")
        parser = JmapParser(data)
        assert "MyClass" in parser.mappings.types
        sm = parser.mappings.types["MyClass"]
        assert sm.super_type == "SomeParent"

    def test_parse_script_struct(self):
        root = {
            "objects": {
                "MyStruct": {
                    "type": "ScriptStruct",
                    "properties": [
                        {"name": "X", "type": "FloatProperty"},
                        {"name": "Y", "type": "FloatProperty"},
                    ],
                }
            }
        }
        data = json.dumps(root).encode("utf-8")
        parser = JmapParser(data)
        assert "MyStruct" in parser.mappings.types

    def test_parse_with_nested_dict_property(self):
        root = {
            "objects": {
                "MyStruct": {
                    "type": "Class",
                    "properties": [
                        {
                            "name": "Items",
                            "type": "ArrayProperty",
                            "inner": {"type": "IntProperty"},
                        }
                    ],
                }
            }
        }
        data = json.dumps(root).encode("utf-8")
        parser = JmapParser(data)
        sm = parser.mappings.types["MyStruct"]
        prop = sm.property_by_name("Items")
        assert prop is not None
        assert prop.mapping_type.inner_type is not None
        assert prop.mapping_type.inner_type.type == "IntProperty"

    def test_gzip_compressed_via_file(self):
        """JmapParser 通过文件路径加载时应支持 .gz 解压。"""
        import tempfile, os
        root = {"objects": {}}
        raw = json.dumps(root).encode("utf-8")
        compressed = gzip.compress(raw)
        with tempfile.NamedTemporaryFile(suffix=".jmap.gz", delete=False) as f:
            f.write(compressed)
            f.flush()
            path = f.name
        try:
            parser = JmapParser(path)
            assert parser.mappings.types == {}
        finally:
            os.unlink(path)


# ============================================================================
# TypeMappingsProvider
# ============================================================================


class TestTypeMappingsProvider:
    """TypeMappingsProvider 应正确加载映射文件。"""

    def test_from_jmap_bytes(self):
        root = {"objects": {}}
        data = json.dumps(root).encode("utf-8")
        provider = TypeMappingsProvider(JmapParser(data).mappings)
        assert isinstance(provider.mappings, TypeMappings)

    def test_unsupported_extension_raises(self):
        with pytest.raises(ParseError, match="[Uu]nsupported mapping file type|[Uu]nsupported.*mapping"):
            TypeMappingsProvider.from_file("test.xyz")
