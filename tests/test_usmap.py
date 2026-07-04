"""Usmap 解析器单元测试 — 验证 .usmap 文件解析和数据模型。"""
from __future__ import annotations

import struct

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.parsers.usmap import (
    MAGIC_USMAP,
    PROPERTY_TYPE_NAMES,
    UsmapData,
    UsmapProperty,
    UsmapSchema,
    _BytesReader,
    _parse_usmap_data,
    parse_usmap,
)


# ============================================================================
# 辅助函数 — 构造合成 .usmap 二进制数据
# ============================================================================

def _build_usmap_v0(
    name_table: list[str] | None = None,
    enums: dict[str, dict[int, str]] | None = None,
    schemas: list[UsmapSchema] | None = None,
) -> bytes:
    """构造一个合成的 v0 .usmap 二进制数据。

    v0 格式（无版本头）:
        Header: magic(u16) + version(u8) + compression(u8) + comp_size(u32) + decomp_size(u32)
        Payload (无压缩):
            NameTable: count(u32) + names[length(u16) + bytes]
            EnumTable: count(u32) + enums[...]
            SchemaTable: count(u32) + schemas[...]
    """
    if name_table is None:
        name_table = []
    if enums is None:
        enums = {}
    if schemas is None:
        schemas = []

    # 构建 payload
    payload = bytearray()

    # NameTable — v0 用 u8 存储名称长度
    payload += struct.pack("<I", len(name_table))
    for name in name_table:
        encoded = name.encode("utf-8")
        payload += struct.pack("<B", len(encoded))
        payload += encoded

    # EnumTable
    payload += struct.pack("<I", len(enums))
    for enum_name, values in enums.items():
        # 枚举名通过 LUT 索引引用
        enum_name_idx = name_table.index(enum_name) if enum_name in name_table else -1
        payload += struct.pack("<i", enum_name_idx)
        # v0 用 u8 存储 value_count
        payload += struct.pack("<B", len(values))
        for val, member_name in values.items():
            # v0: 值通过索引存储（成员名在 name table 中的索引）
            member_idx = name_table.index(member_name) if member_name in name_table else -1
            payload += struct.pack("<i", member_idx)

    # SchemaTable
    payload += struct.pack("<I", len(schemas))
    for schema in schemas:
        name_idx = name_table.index(schema.name) if schema.name in name_table else -1
        super_idx = name_table.index(schema.super_type) if schema.super_type and schema.super_type in name_table else -1
        payload += struct.pack("<i", name_idx)
        payload += struct.pack("<i", super_idx)
        payload += struct.pack("<H", schema.property_count)
        payload += struct.pack("<H", schema.serializable_count)
        # 按序号排序属性
        sorted_props = sorted(schema.properties.values(), key=lambda p: p.index)
        for prop in sorted_props:
            payload += struct.pack("<H", prop.index)
            payload += struct.pack("<B", prop.array_dim)
            prop_name_idx = name_table.index(prop.name) if prop.name in name_table else -1
            payload += struct.pack("<i", prop_name_idx)
            # 属性类型
            _write_property_type(payload, prop)

    # 组装完整文件
    comp_size = len(payload)
    header = bytearray()
    header += struct.pack("<H", MAGIC_USMAP)  # magic
    header += struct.pack("<B", 0)  # version
    header += struct.pack("<B", 0)  # compression = none
    header += struct.pack("<I", comp_size)  # compressed size
    header += struct.pack("<I", comp_size)  # uncompressed size
    header += bytes(payload)

    return bytes(header)


def _write_property_type(buf: bytearray, prop: UsmapProperty) -> None:
    """向缓冲区写入属性类型（递归）。"""
    # 查找类型 ID
    type_id = None
    for tid, tname in PROPERTY_TYPE_NAMES.items():
        if tname == prop.type_name:
            type_id = tid
            break
    if type_id is None:
        type_id = 0xFF  # Unknown
    buf += struct.pack("<B", type_id)

    if prop.type_name == "EnumProperty":
        if prop.inner_type:
            _write_property_type(buf, prop.inner_type)
        # enum name 在 name table 中
        buf += struct.pack("<i", -1)  # placeholder
    elif prop.type_name == "StructProperty":
        buf += struct.pack("<i", -1)  # struct name placeholder
    elif prop.type_name in {"ArrayProperty", "SetProperty", "OptionalProperty"}:
        if prop.inner_type:
            _write_property_type(buf, prop.inner_type)
    elif prop.type_name == "MapProperty":
        if prop.inner_type:
            _write_property_type(buf, prop.inner_type)
        if prop.value_type:
            _write_property_type(buf, prop.value_type)


# ============================================================================
# Header 解析测试
# ============================================================================

class TestUsmapHeader:
    """验证 .usmap 文件头解析。"""

    def test_valid_magic(self):
        """有效 magic 0x30C4 应正常解析。"""
        data = _build_usmap_v0()
        result = _parse_usmap_data(data)
        assert result.version == 0

    def test_invalid_magic_raises(self):
        """无效 magic 应抛出 ParseError。"""
        data = struct.pack("<H", 0x1234) + b"\x00" * 20
        with pytest.raises(ParseError, match="magic 无效"):
            _parse_usmap_data(data)

    def test_truncated_header(self):
        """截断的文件头应抛出 ParseError。"""
        data = struct.pack("<H", MAGIC_USMAP)  # 只有 magic，缺字段
        with pytest.raises(ParseError, match="读取越界"):
            _parse_usmap_data(data)

    def test_version_too_high(self):
        """超出支持范围的版本号应抛出 ParseError。"""
        buf = bytearray()
        buf += struct.pack("<H", MAGIC_USMAP)
        buf += struct.pack("<B", 99)  # 无效版本
        with pytest.raises(ParseError, match="版本不支持"):
            _parse_usmap_data(bytes(buf))


# ============================================================================
# NameTable 解析测试
# ============================================================================

class TestUsmapNameTable:
    """验证 NameTable 解析。"""

    def test_empty_name_table(self):
        """空 NameTable 应正常解析。"""
        data = _build_usmap_v0(name_table=[])
        result = _parse_usmap_data(data)
        assert result.name_table == []

    def test_single_name(self):
        """单个名称应正确解析。"""
        data = _build_usmap_v0(name_table=["TestStruct"])
        result = _parse_usmap_data(data)
        assert result.name_table == ["TestStruct"]

    def test_multiple_names(self):
        """多个名称应按序解析。"""
        names = ["A", "BB", "CCC", "DDDD"]
        data = _build_usmap_v0(name_table=names)
        result = _parse_usmap_data(data)
        assert result.name_table == names

    def test_unicode_name(self):
        """Unicode 名称应正确解码。"""
        data = _build_usmap_v0(name_table=["Hello", "测试"])
        result = _parse_usmap_data(data)
        assert result.name_table[1] == "测试"


# ============================================================================
# SchemaTable 解析测试
# ============================================================================

class TestUsmapSchemaTable:
    """验证 SchemaTable 解析。"""

    def test_empty_schemas(self):
        """空 schema 列表应正常解析。"""
        data = _build_usmap_v0(schemas=[])
        result = _parse_usmap_data(data)
        assert result.schemas == {}

    def test_single_schema_no_properties(self):
        """无属性的 schema 应正确解析。"""
        schema = UsmapSchema(
            name="MyClass",
            super_type=None,
            property_count=0,
            serializable_count=0,
        )
        data = _build_usmap_v0(name_table=["MyClass"], schemas=[schema])
        result = _parse_usmap_data(data)
        assert "MyClass" in result.schemas
        parsed = result.schemas["MyClass"]
        assert parsed.name == "MyClass"
        assert parsed.super_type is None
        assert parsed.property_count == 0
        assert parsed.properties == {}

    def test_schema_with_int_property(self):
        """包含 IntProperty 的 schema 应正确解析。"""
        prop = UsmapProperty(
            index=0, name="Health", type_name="IntProperty", array_dim=1,
        )
        schema = UsmapSchema(
            name="Character",
            super_type=None,
            property_count=1,
            serializable_count=1,
            properties={0: prop},
        )
        data = _build_usmap_v0(name_table=["Character", "Health"], schemas=[schema])
        result = _parse_usmap_data(data)
        parsed = result.schemas["Character"]
        assert len(parsed.properties) == 1
        assert parsed.properties[0].name == "Health"
        assert parsed.properties[0].type_name == "IntProperty"

    def test_schema_with_array_property(self):
        """包含 ArrayProperty 的 schema 应正确解析。"""
        inner = UsmapProperty(index=0, name="", type_name="FloatProperty")
        prop = UsmapProperty(
            index=0, name="Scores", type_name="ArrayProperty",
            inner_type=inner, array_dim=1,
        )
        schema = UsmapSchema(
            name="Player",
            property_count=1,
            serializable_count=1,
            properties={0: prop},
        )
        data = _build_usmap_v0(name_table=["Player", "Scores"], schemas=[schema])
        result = _parse_usmap_data(data)
        parsed = result.schemas["Player"]
        assert parsed.properties[0].type_name == "ArrayProperty"

    def test_schema_with_super_type(self):
        """带父类的 schema 应正确解析 super_type。"""
        schema = UsmapSchema(
            name="Child",
            super_type="Parent",
            property_count=0,
            serializable_count=0,
        )
        data = _build_usmap_v0(
            name_table=["Child", "Parent"], schemas=[schema],
        )
        result = _parse_usmap_data(data)
        parsed = result.schemas["Child"]
        assert parsed.super_type == "Parent"


# ============================================================================
# UsmapData 公共 API 测试
# ============================================================================

class TestUsmapDataAPI:
    """验证 UsmapData 的公共方法。"""

    def test_from_bytes(self):
        """从 bytes 构造 UsmapData。"""
        data = _build_usmap_v0(name_table=["Test"])
        usmap = UsmapData(data)
        assert usmap.version == 0
        assert usmap.name_table == ["Test"]

    def test_from_path(self, tmp_path):
        """从文件路径构造 UsmapData。"""
        data = _build_usmap_v0(name_table=["FileTest"])
        path = tmp_path / "test.usmap"
        path.write_bytes(data)
        usmap = UsmapData(str(path))
        assert usmap.name_table == ["FileTest"]

    def test_parse_usmap_function(self):
        """parse_usmap() 便捷函数应正常工作。"""
        data = _build_usmap_v0(name_table=["FuncTest"])
        usmap = parse_usmap(data)
        assert usmap.name_table == ["FuncTest"]

    def test_invalid_file_extension(self, tmp_path):
        """非 .usmap/.jmap 文件应抛出 ParseError。"""
        path = tmp_path / "test.txt"
        path.write_bytes(b"hello")
        with pytest.raises(ParseError, match="不支持的映射文件类型"):
            UsmapData(str(path))

    def test_get_schema(self):
        """get_schema() 应支持短名和全限定名。"""
        schema = UsmapSchema(name="MyStruct", property_count=0)
        data = _build_usmap_v0(name_table=["MyStruct"], schemas=[schema])
        usmap = UsmapData(data)
        assert usmap.get_schema("MyStruct") is not None
        assert usmap.get_schema("SomePackage.MyStruct") is not None
        assert usmap.get_schema("Nonexistent") is None
        assert usmap.get_schema(None) is None

    def test_find_property(self):
        """find_property() 应在父类链中查找属性。"""
        prop = UsmapProperty(index=0, name="ID", type_name="IntProperty")
        schema = UsmapSchema(
            name="Entity",
            property_count=1,
            serializable_count=1,
            properties={0: prop},
        )
        data = _build_usmap_v0(name_table=["Entity", "ID"], schemas=[schema])
        usmap = UsmapData(data)
        found = usmap.find_property("Entity", "ID")
        assert found is not None
        assert found.name == "ID"
        # 大小写不敏感
        found_upper = usmap.find_property("Entity", "id")
        assert found_upper is not None

    def test_find_property_not_found(self):
        """find_property() 找不到时返回 None。"""
        schema = UsmapSchema(name="Empty", property_count=0)
        data = _build_usmap_v0(name_table=["Empty"], schemas=[schema])
        usmap = UsmapData(data)
        assert usmap.find_property("Empty", "Nonexistent") is None


# ============================================================================
# EnumTable 解析测试
# ============================================================================

class TestUsmapEnumTable:
    """验证 EnumTable 解析。"""

    def test_empty_enums(self):
        """空枚举表应正常解析。"""
        data = _build_usmap_v0(enums={})
        result = _parse_usmap_data(data)
        assert result.enums == {}

    def test_enum_with_values(self):
        """包含值的枚举应正确解析。"""
        names = ["ETestEnum", "Value1", "Value2"]
        enums = {
            "ETestEnum": {0: "Value1", 1: "Value2"},
        }
        data = _build_usmap_v0(name_table=names, enums=enums)
        result = _parse_usmap_data(data)
        assert "ETestEnum" in result.enums
        assert result.enums["ETestEnum"][0] == "Value1"
        assert result.enums["ETestEnum"][1] == "Value2"


# ============================================================================
# _BytesReader 内部测试
# ============================================================================

class TestBytesReader:
    """验证内部二进制读取器。"""

    def test_read_u8(self):
        reader = _BytesReader(b"\x42")
        assert reader.u8() == 0x42

    def test_read_u16(self):
        reader = _BytesReader(struct.pack("<H", 12345))
        assert reader.u16() == 12345

    def test_read_u32(self):
        reader = _BytesReader(struct.pack("<I", 0xDEADBEEF))
        assert reader.u32() == 0xDEADBEEF

    def test_read_i32(self):
        reader = _BytesReader(struct.pack("<i", -42))
        assert reader.i32() == -42

    def test_read_u64(self):
        reader = _BytesReader(struct.pack("<Q", 0x123456789ABCDEF0))
        assert reader.u64() == 0x123456789ABCDEF0

    def test_read_overflow(self):
        reader = _BytesReader(b"\x01")
        with pytest.raises(ParseError, match="读取越界"):
            reader.read(2)

    def test_remaining(self):
        reader = _BytesReader(b"\x01\x02\x03")
        assert reader.remaining == 3
        reader.u8()
        assert reader.remaining == 2

    def test_name_lookup(self):
        lut = ["alpha", "beta", "gamma"]
        reader = _BytesReader(struct.pack("<i", 1))
        assert reader.name(lut) == "beta"

    def test_name_none(self):
        lut = ["alpha"]
        reader = _BytesReader(struct.pack("<i", -1))
        assert reader.name(lut) is None

    def test_name_out_of_bounds(self):
        lut = ["alpha"]
        reader = _BytesReader(struct.pack("<i", 5))
        with pytest.raises(ParseError, match="名称索引越界"):
            reader.name(lut)


# ============================================================================
# 外部 .usmap 文件集成测试（如有测试样本）
# ============================================================================

class TestUsmapIntegration:
    """外部 .usmap 文件集成测试。"""

    @pytest.fixture
    def sample_usmap(self):
        """尝试定位外部测试样本。"""
        import os
        base = os.path.join(
            os.path.dirname(__file__), "..", "external",
            "UAssetAPI", "UAssetAPI.Tests", "TestAssets", "TestJson",
        )
        path = os.path.join(base, "MotorTown.usmap")
        if os.path.exists(path):
            return path
        pytest.skip("无外部 .usmap 测试样本")

    def test_load_real_usmap(self, sample_usmap):
        """加载真实 .usmap 文件应成功。"""
        usmap = UsmapData(sample_usmap)
        assert usmap.version >= 0
        assert isinstance(usmap.name_table, list)
        assert isinstance(usmap.schemas, dict)

    def test_parse_usmap_function_real(self, sample_usmap):
        """parse_usmap() 加载真实文件应成功。"""
        usmap = parse_usmap(sample_usmap)
        assert len(usmap.schemas) > 0
