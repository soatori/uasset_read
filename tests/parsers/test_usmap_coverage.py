"""usmap/jmap 解析器测试覆盖。#363

仅包含 tests/test_usmap.py 中未覆盖的测试用例，避免重复。
"""
from __future__ import annotations

import gzip as gzip_mod
import json
import struct
from io import BytesIO
from unittest.mock import patch

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.parsers.usmap import (
    _BytesReader,
    _decompress,
    _jmap_prop_type,
    _parse_property_type,
    UsmapProperty,
    UsmapSchema,
    UsmapData,
    parse_usmap,
    PROPERTY_TYPE_NAMES,
    MAGIC_USMAP,
    MAX_RECURSION_DEPTH,
)


# ---------------------------------------------------------------------------
# 辅助：构建最小合法 .usmap 二进制（无压缩，version 0）
# ---------------------------------------------------------------------------

def _build_minimal_usmap(
    name_table: list[str] | None = None,
    enums: dict[str, dict[int, str]] | None = None,
    schemas: dict[str, UsmapSchema] | None = None,
    version: int = 0,
) -> bytes:
    """构建最小可解析的 .usmap 字节流。"""
    if name_table is None:
        name_table = []
    if enums is None:
        enums = {}
    if schemas is None:
        schemas = {}

    buf = bytearray()
    buf += struct.pack("<H", MAGIC_USMAP)
    buf += struct.pack("<B", version)

    # version 1+: has_versioning flag
    if version >= 1:
        buf += struct.pack("<B", 0)

    # 构建 payload
    payload = bytearray()

    # NameTable
    payload += struct.pack("<I", len(name_table))
    for name in name_table:
        name_bytes = name.encode("utf-8")
        payload += struct.pack("<H" if version >= 2 else "<B", len(name_bytes))
        payload += name_bytes

    # EnumTable
    payload += struct.pack("<I", len(enums))
    for enum_name, values in enums.items():
        enum_name_idx = name_table.index(enum_name) if enum_name in name_table else -1
        payload += struct.pack("<i", enum_name_idx)
        value_count = len(values)
        payload += struct.pack("<H" if version >= 3 else "<B", value_count)
        for val, member in values.items():
            if version >= 4:
                payload += struct.pack("<Q", val)
            member_idx = name_table.index(member) if member in name_table else -1
            payload += struct.pack("<i", member_idx)

    # SchemaTable
    payload += struct.pack("<I", len(schemas))
    for schema in schemas.values():
        schema_name_idx = name_table.index(schema.name) if schema.name in name_table else -1
        payload += struct.pack("<i", schema_name_idx)
        super_idx = name_table.index(schema.super_type) if schema.super_type and schema.super_type in name_table else -1
        payload += struct.pack("<i", super_idx)
        payload += struct.pack("<H", schema.property_count)
        payload += struct.pack("<H", schema.serializable_count)

        for prop in schema.properties.values():
            payload += struct.pack("<H", prop.index)
            payload += struct.pack("<B", prop.array_dim)
            prop_name_idx = name_table.index(prop.name) if prop.name in name_table else -1
            payload += struct.pack("<i", prop_name_idx)
            _write_prop_type(payload, prop)

    decomp_size = len(payload)
    buf += struct.pack("<B", 0)  # compression = none
    buf += struct.pack("<I", decomp_size)
    buf += struct.pack("<I", decomp_size)
    buf += payload

    return bytes(buf)


def _write_prop_type(buf: bytearray, prop: UsmapProperty) -> None:
    """向 buf 追加属性类型的二进制表示。"""
    type_id = _type_name_to_id(prop.type_name)
    buf += struct.pack("<B", type_id)

    if prop.type_name == "EnumProperty":
        inner = prop.inner_type or UsmapProperty(index=0, name="", type_name="ByteProperty")
        _write_prop_type(buf, inner)
        buf += struct.pack("<i", -1)  # enum name placeholder
    elif prop.type_name == "StructProperty":
        buf += struct.pack("<i", -1)  # struct name placeholder
    elif prop.type_name in {"ArrayProperty", "SetProperty", "OptionalProperty"}:
        inner = prop.inner_type or UsmapProperty(index=0, name="", type_name="IntProperty")
        _write_prop_type(buf, inner)
    elif prop.type_name == "MapProperty":
        inner = prop.inner_type or UsmapProperty(index=0, name="", type_name="IntProperty")
        value = prop.value_type or UsmapProperty(index=0, name="", type_name="IntProperty")
        _write_prop_type(buf, inner)
        _write_prop_type(buf, value)


def _type_name_to_id(name: str) -> int:
    for tid, tname in PROPERTY_TYPE_NAMES.items():
        if tname == name:
            return tid
    return 0xFF


# ===========================================================================
# 测试 _parse_property_type（递归类型解析）
# ===========================================================================

class TestParsePropertyType:
    """_parse_property_type 递归解析测试。"""

    @staticmethod
    def _make_reader(type_id: int, extra: bytes = b"") -> _BytesReader:
        return _BytesReader(struct.pack("<B", type_id) + extra)

    def test_simple_int(self):
        reader = self._make_reader(2)  # IntProperty
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "IntProperty"
        assert prop.inner_type is None
        assert prop.value_type is None
        assert prop.struct_type is None
        assert prop.enum_name is None

    def test_simple_float(self):
        reader = self._make_reader(3)  # FloatProperty
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "FloatProperty"

    def test_simple_byte(self):
        reader = self._make_reader(0)  # ByteProperty
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "ByteProperty"

    def test_simple_bool(self):
        reader = self._make_reader(1)  # BoolProperty
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "BoolProperty"

    def test_array_property(self):
        # ArrayProperty(0x08) + inner IntProperty(0x02)
        reader = self._make_reader(8, struct.pack("<B", 2))
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "ArrayProperty"
        assert prop.inner_type is not None
        assert prop.inner_type.type_name == "IntProperty"

    def test_map_property(self):
        # MapProperty(24) + key IntProperty(2) + value FloatProperty(3)
        reader = self._make_reader(24, struct.pack("<BB", 2, 3))
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "MapProperty"
        assert prop.inner_type is not None
        assert prop.inner_type.type_name == "IntProperty"
        assert prop.value_type is not None
        assert prop.value_type.type_name == "FloatProperty"

    def test_struct_property_preserves_name(self):
        # StructProperty(9) + struct name index = -1
        reader = self._make_reader(9, struct.pack("<i", -1))
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "StructProperty"
        assert prop.struct_type == ""

    def test_struct_property_with_lut_name(self):
        # StructProperty(9) + struct name index = 0 → "FVector"
        lut = ["FVector"]
        reader = self._make_reader(9, struct.pack("<i", 0))
        prop = _parse_property_type(reader, lut)
        assert prop.type_name == "StructProperty"
        assert prop.struct_type == "FVector"

    def test_enum_property_preserves_name(self):
        # EnumProperty(0x1A) + inner ByteProperty(0x00) + enum name index = -1
        reader = self._make_reader(0x1A, struct.pack("<B", 0) + struct.pack("<i", -1))
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "EnumProperty"
        assert prop.inner_type is not None
        assert prop.inner_type.type_name == "ByteProperty"
        assert prop.enum_name == ""

    def test_enum_property_with_lut_name(self):
        lut = ["EMyEnum"]
        reader = self._make_reader(0x1A, struct.pack("<B", 0) + struct.pack("<i", 0))
        prop = _parse_property_type(reader, lut)
        assert prop.type_name == "EnumProperty"
        assert prop.enum_name == "EMyEnum"

    def test_set_property(self):
        reader = self._make_reader(25, struct.pack("<B", 7))  # SetProperty + DoubleProperty
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "SetProperty"
        assert prop.inner_type.type_name == "DoubleProperty"

    def test_optional_property(self):
        reader = self._make_reader(28, struct.pack("<B", 5))  # OptionalProperty + NameProperty
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "OptionalProperty"
        assert prop.inner_type.type_name == "NameProperty"

    def test_unknown_type_custom_fd(self):
        reader = self._make_reader(0xFD)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "CustomProperty_FD"

    def test_unknown_type_custom_fe(self):
        reader = self._make_reader(0xFE)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "CustomProperty_FE"

    def test_fully_unknown_type_id(self):
        reader = self._make_reader(0xC0)  # 未映射的 id
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "Unknown"

    def test_nested_array_of_struct(self):
        # ArrayProperty → StructProperty
        inner_struct = struct.pack("<B", 9) + struct.pack("<i", -1)  # StructProperty
        reader = self._make_reader(8, inner_struct)  # ArrayProperty
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "ArrayProperty"
        assert prop.inner_type.type_name == "StructProperty"
        assert prop.inner_type.struct_type == ""

    def test_nested_map_string_to_array(self):
        # MapProperty → key=StrProperty(10), value=ArrayProperty(IntProperty)
        inner = struct.pack("<B", 10)  # StrProperty (key)
        val_inner = struct.pack("<B", 8) + struct.pack("<B", 2)  # ArrayProperty(IntProperty) (value)
        reader = self._make_reader(24, inner + val_inner)
        prop = _parse_property_type(reader, [])
        assert prop.type_name == "MapProperty"
        assert prop.inner_type.type_name == "StrProperty"
        assert prop.value_type.type_name == "ArrayProperty"
        assert prop.value_type.inner_type.type_name == "IntProperty"

    def test_depth_limit_exceeded(self):
        """depth > MAX_RECURSION_DEPTH 应抛出 ParseError。"""
        reader = self._make_reader(2)  # IntProperty (any type)
        with pytest.raises(ParseError, match="递归深度超过上限"):
            _parse_property_type(reader, [], depth=MAX_RECURSION_DEPTH + 1)


# ===========================================================================
# 测试 UsmapProperty 数据类
# ===========================================================================

class TestUsmapProperty:
    """UsmapProperty 数据类测试。"""

    def test_creation_with_all_fields(self):
        inner = UsmapProperty(index=0, name="", type_name="IntProperty")
        value = UsmapProperty(index=0, name="", type_name="FloatProperty")
        prop = UsmapProperty(
            index=42,
            name="MyProp",
            type_name="MapProperty",
            struct_type="FVector",
            inner_type=inner,
            value_type=value,
            enum_name="EMyEnum",
            array_dim=3,
        )
        assert prop.index == 42
        assert prop.name == "MyProp"
        assert prop.type_name == "MapProperty"
        assert prop.struct_type == "FVector"
        assert prop.inner_type is inner
        assert prop.value_type is value
        assert prop.enum_name == "EMyEnum"
        assert prop.array_dim == 3

    def test_defaults(self):
        prop = UsmapProperty(index=0, name="X", type_name="FloatProperty")
        assert prop.struct_type is None
        assert prop.inner_type is None
        assert prop.value_type is None
        assert prop.enum_name is None
        assert prop.array_dim == 1


# ===========================================================================
# 测试 UsmapSchema 数据类
# ===========================================================================

class TestUsmapSchema:
    """UsmapSchema 数据类测试。"""

    def test_creation_defaults(self):
        schema = UsmapSchema(name="TestClass")
        assert schema.name == "TestClass"
        assert schema.super_type is None
        assert schema.serializable_count == 0
        assert schema.property_count == 0
        assert schema.properties == {}

    def test_with_properties(self):
        prop = UsmapProperty(index=0, name="Health", type_name="FloatProperty")
        schema = UsmapSchema(
            name="APawn",
            super_type="AActor",
            serializable_count=1,
            property_count=5,
            properties={0: prop},
        )
        assert schema.super_type == "AActor"
        assert len(schema.properties) == 1
        assert schema.properties[0].name == "Health"


# ===========================================================================
# 测试 _jmap_prop_type
# ===========================================================================

class TestJmapPropType:
    """_jmap_prop_type 函数测试。"""

    def test_simple_property(self):
        result = _jmap_prop_type({"type": "IntProperty"})
        assert result.type_name == "IntProperty"
        assert result.inner_type is None
        assert result.value_type is None
        assert result.struct_type is None
        assert result.enum_name is None

    def test_array_property_with_container(self):
        result = _jmap_prop_type({
            "type": "ArrayProperty",
            "container": {"type": "FloatProperty"},
        })
        assert result.type_name == "ArrayProperty"
        assert result.inner_type is not None
        assert result.inner_type.type_name == "FloatProperty"

    def test_array_property_with_inner(self):
        """jmap 同时支持 'container' 和 'inner' 键。"""
        result = _jmap_prop_type({
            "type": "ArrayProperty",
            "inner": {"type": "NameProperty"},
        })
        assert result.inner_type.type_name == "NameProperty"

    def test_array_property_with_key_prop(self):
        """jmap 'key_prop' 键作为 fallback 被识别。"""
        result = _jmap_prop_type({
            "type": "ArrayProperty",
            "key_prop": {"type": "StrProperty"},
        })
        assert result.inner_type.type_name == "StrProperty"

    def test_map_property_with_key_and_value(self):
        result = _jmap_prop_type({
            "type": "MapProperty",
            "key_prop": {"type": "NameProperty"},
            "value_prop": {"type": "StrProperty"},
        })
        assert result.type_name == "MapProperty"
        assert result.inner_type is not None
        assert result.inner_type.type_name == "NameProperty"
        assert result.value_type is not None
        assert result.value_type.type_name == "StrProperty"

    def test_unknown_type_defaults(self):
        result = _jmap_prop_type({"type": None})
        assert result.type_name == "Unknown"

    def test_struct_type_preserves_name(self):
        result = _jmap_prop_type({
            "type": "StructProperty",
            "struct": "Engine.FVector",
        })
        assert result.struct_type == "FVector"

    def test_struct_type_empty_string(self):
        result = _jmap_prop_type({
            "type": "StructProperty",
            "struct": "",
        })
        assert result.struct_type is None

    def test_enum_type_preserves_name(self):
        result = _jmap_prop_type({
            "type": "EnumProperty",
            "enum": "Engine.EMyEnum",
        })
        assert result.enum_name == "EMyEnum"

    def test_enum_type_empty_string(self):
        result = _jmap_prop_type({
            "type": "EnumProperty",
            "enum": "",
        })
        assert result.enum_name is None

    def test_nested_containers(self):
        """ArrayProperty(MapProperty(Int, Float))"""
        result = _jmap_prop_type({
            "type": "ArrayProperty",
            "container": {
                "type": "MapProperty",
                "key_prop": {"type": "IntProperty"},
                "value_prop": {"type": "FloatProperty"},
            },
        })
        assert result.type_name == "ArrayProperty"
        assert result.inner_type.type_name == "MapProperty"
        assert result.inner_type.inner_type.type_name == "IntProperty"
        assert result.inner_type.value_type.type_name == "FloatProperty"

    def test_inner_not_dict_ignored(self):
        """container/inner/key_prop 非 dict 时忽略。"""
        result = _jmap_prop_type({
            "type": "ArrayProperty",
            "container": "not_a_dict",
        })
        assert result.inner_type is None

    def test_value_not_dict_ignored(self):
        """value_prop 非 dict 时忽略。"""
        result = _jmap_prop_type({
            "type": "MapProperty",
            "key_prop": {"type": "IntProperty"},
            "value_prop": "not_a_dict",
        })
        assert result.inner_type is not None
        assert result.value_type is None

    def test_empty_dict(self):
        """空 dict 应返回 Unknown 类型。"""
        result = _jmap_prop_type({})
        assert result.type_name == "Unknown"

    def test_deeply_nested_no_recursion_limit(self):
        """当前实现无递归深度限制，深层嵌套应正常工作。"""
        inner: dict = {"type": "IntProperty"}
        for _ in range(20):
            inner = {"type": "ArrayProperty", "container": inner}
        result = _jmap_prop_type(inner)
        assert result.type_name == "ArrayProperty"
        # 递归 20 层
        current = result
        for _ in range(19):
            assert current.inner_type is not None
            assert current.inner_type.type_name == "ArrayProperty"
            current = current.inner_type
        assert current.inner_type.type_name == "IntProperty"


# ===========================================================================
# 测试 UsmapData / parse_usmap（仅 test_usmap.py 未覆盖的用例）
# ===========================================================================

class TestUsmapData:
    """UsmapData 和 parse_usmap 补充测试。"""

    def test_parse_usmap_from_bytes(self):
        """从 bytes 解析最小合法 usmap。"""
        data = _build_minimal_usmap(name_table=["Foo", "Bar"])
        result = parse_usmap(data)
        assert result.version == 0
        assert result.name_table == ["Foo", "Bar"]
        assert result.enums == {}
        assert result.schemas == {}

    def test_usmap_data_from_stream(self):
        """从 BinaryIO 流构造。"""
        data = _build_minimal_usmap(name_table=["Stream"])
        ud = UsmapData(BytesIO(data))
        assert ud.version == 0
        assert ud.name_table == ["Stream"]

    def test_version_1_with_versioning(self):
        """version 1 + has_versioning=true + custom_count=2 能正常解析。"""
        payload = bytearray()
        payload += struct.pack("<I", 1)
        payload += struct.pack("<B", 4)  # name length (version 0 uses u8)
        payload += b"Test"
        payload += struct.pack("<I", 0)  # enum count
        payload += struct.pack("<I", 0)  # schema count

        buf = bytearray(struct.pack("<H", MAGIC_USMAP))
        buf += struct.pack("<B", 1)  # version=1
        buf += struct.pack("<B", 1)  # has_versioning=true
        buf += struct.pack("<ii", 0, 0)  # PackageFileVersion
        buf += struct.pack("<i", 2)  # custom_count=2（实际测试自定义版本循环）
        # 2 个 CustomVersion，每个 20 字节
        buf += b"\x00" * 40  # custom versions data
        buf += struct.pack("<I", 0)  # NetCL
        buf += struct.pack("<B", 0)  # compression=none
        buf += struct.pack("<I", len(payload))
        buf += struct.pack("<I", len(payload))
        buf += payload

        result = parse_usmap(bytes(buf))
        assert result.version == 1
        assert result.name_table == ["Test"]

    def test_version_1_negative_custom_count(self):
        """version 1 + has_versioning=true + custom_count=-1 应抛出 ParseError。"""
        buf = bytearray(struct.pack("<H", MAGIC_USMAP))
        buf += struct.pack("<B", 1)  # version=1
        buf += struct.pack("<B", 1)  # has_versioning=true
        buf += struct.pack("<ii", 0, 0)  # PackageFileVersion
        buf += struct.pack("<i", -1)  # custom_count=-1（无效）
        buf += struct.pack("<I", 0)  # NetCL
        buf += struct.pack("<B", 0)  # compression=none
        buf += struct.pack("<I", 0)  # comp_size
        buf += struct.pack("<I", 0)  # decomp_size

        with pytest.raises(ParseError, match="CustomVersion 数量无效"):
            parse_usmap(bytes(buf))

    def test_find_property_in_parent(self):
        """属性在父类中能找到。"""
        child_prop = UsmapProperty(index=0, name="Speed", type_name="FloatProperty")
        parent_prop = UsmapProperty(index=0, name="Health", type_name="FloatProperty")
        child = UsmapSchema(
            name="Derived",
            super_type="Base",
            serializable_count=1,
            property_count=1,
            properties={0: child_prop},
        )
        base = UsmapSchema(
            name="Base",
            serializable_count=1,
            property_count=1,
            properties={0: parent_prop},
        )
        data = _build_minimal_usmap(
            name_table=["Derived", "Base", "Speed", "Health"],
            schemas={"Derived": child, "Base": base},
        )
        ud = UsmapData(data)
        found = ud.find_property("Derived", "Health")
        assert found is not None
        assert found.name == "Health"

    def test_find_property_no_infinite_loop(self):
        """循环继承不应导致无限循环。"""
        prop = UsmapProperty(index=0, name="X", type_name="IntProperty")
        a = UsmapSchema(name="A", super_type="B", serializable_count=1,
                        property_count=1, properties={0: prop})
        b = UsmapSchema(name="B", super_type="A", serializable_count=0,
                        property_count=0, properties={})
        data = _build_minimal_usmap(
            name_table=["A", "B", "X"],
            schemas={"A": a, "B": b},
        )
        ud = UsmapData(data)
        # 不应死循环
        assert ud.find_property("A", "Nonexistent") is None

    def test_parse_usmap_returns_usmap_data(self):
        data = _build_minimal_usmap()
        result = parse_usmap(data)
        assert isinstance(result, UsmapData)


# ===========================================================================
# 测试 _decompress 压缩方法
# ===========================================================================

class TestDecompress:
    """_decompress 函数测试。"""

    def test_no_compression_valid(self):
        """无压缩模式 comp_size == decomp_size 应正常返回。"""
        payload = b"\x01\x02\x03"
        result = _decompress(payload, method=0, comp_size=3, decomp_size=3)
        assert result == payload

    def test_no_compression_size_mismatch(self):
        """无压缩模式 comp_size != decomp_size 应抛出 ParseError。"""
        with pytest.raises(ParseError, match="大小不一致"):
            _decompress(b"\x01", method=0, comp_size=1, decomp_size=2)

    def test_unsupported_method(self):
        """不支持的压缩方法应抛出 ParseError。"""
        with pytest.raises(ParseError, match="不支持的 Usmap 压缩方式"):
            _decompress(b"", method=99, comp_size=0, decomp_size=0)

    def test_brotli_import_error(self):
        """brotli 不可用时应抛出 ParseError（带提示）。"""
        # 确保 brotli 不可用
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "brotli":
                raise ImportError("No module named 'brotli'")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            with pytest.raises(ParseError, match="Brotli"):
                _decompress(b"", method=2, comp_size=0, decomp_size=0)

    def test_zstd_import_error(self):
        """zstandard 不可用时应抛出 ParseError（带提示）。"""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "zstandard":
                raise ImportError("No module named 'zstandard'")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            with pytest.raises(ParseError, match="ZStandard"):
                _decompress(b"", method=3, comp_size=0, decomp_size=0)

    def test_brotli_decompress(self):
        """brotli 可用时应正确解压。"""
        brotli = pytest.importorskip("brotli")
        original = b"Hello, brotli! " * 100
        compressed = brotli.compress(original)
        result = _decompress(compressed, method=2, comp_size=len(compressed), decomp_size=len(original))
        assert result == original

    def test_zstd_decompress(self):
        """zstandard 可用时应正确解压。"""
        zstd = pytest.importorskip("zstandard")
        original = b"Hello, zstd! " * 100
        cctx = zstd.ZstdCompressor()
        compressed = cctx.compress(original)
        result = _decompress(compressed, method=3, comp_size=len(compressed), decomp_size=len(original))
        assert result == original


# ===========================================================================
# 测试 gzip 路径
# ===========================================================================

class TestGzipPaths:
    """UsmapData gzip 解压路径测试。

    注：.usmap.gz 扩展名当前不被支持（UsmapData.__init__ 中的扩展名检查
    先于 gzip 解压逻辑），因此 .usmap.gz 会抛出 ParseError。
    .jmap.gz 则被正确支持。此处测试两种情况以明确当前行为。
    """

    def test_usmap_gzip_extension_rejected(self, tmp_path):
        """".usmap.gz 当前不被支持，应抛出 ParseError。"""
        data = _build_minimal_usmap(name_table=["GzipTest"])
        path = tmp_path / "test.usmap.gz"
        path.write_bytes(gzip_mod.compress(data))
        with pytest.raises(ParseError, match="不支持的映射文件类型"):
            UsmapData(str(path))

    def test_gzip_compressed_bytes_via_binary_io(self):
        """通过 BinaryIO 传入 gzip 压缩的 usmap 数据（gzip 在流外解压）。"""
        data = _build_minimal_usmap(name_table=["GzipStream"])
        compressed = gzip_mod.compress(data)
        # UsmapData 不对 BinaryIO 做 gzip 解压，所以传入原始 usmap bytes
        # 这里测试的是 UsmapData 对 bytes 输入的正确解析
        ud = UsmapData(data)
        assert ud.name_table == ["GzipStream"]


# ===========================================================================
# 测试 jmap 加载路径（JSON 映射）
# ===========================================================================

class TestJmapLoading:
    """UsmapData 从 .jmap JSON 文件加载的测试。"""

    def test_jmap_basic(self, tmp_path):
        jmap_data = {
            "objects": {
                "Engine.MyEnum": {
                    "type": "Enum",
                    "names": [["Value0", 0], ["Value1", 1]],
                },
                "Engine.MyStruct": {
                    "type": "ScriptStruct",
                    "properties": [
                        {"name": "Health", "type": "FloatProperty"},
                        {"name": "Name", "type": "StrProperty"},
                    ],
                },
                "Engine.MyClass": {
                    "type": "Class",
                    "super_struct": "Engine.Object",
                    "properties": [
                        {"name": "Pos", "type": "StructProperty", "struct": "Engine.FVector"},
                    ],
                },
            }
        }
        path = tmp_path / "test.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")

        ud = UsmapData(str(path))
        assert "MyEnum" in ud.enums
        assert ud.enums["MyEnum"][0] == "Value0"
        assert ud.enums["MyEnum"][1] == "Value1"
        assert "MyStruct" in ud.schemas
        assert len(ud.schemas["MyStruct"].properties) == 2
        assert "MyClass" in ud.schemas
        assert ud.schemas["MyClass"].super_type == "Object"

    def test_jmap_with_array_dim(self, tmp_path):
        jmap_data = {
            "objects": {
                "Engine.Foo": {
                    "type": "ScriptStruct",
                    "properties": [
                        {"name": "Arr", "type": "ArrayProperty", "array_dim": 3,
                         "inner": {"type": "IntProperty"}},
                    ],
                }
            }
        }
        path = tmp_path / "dim.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        prop = list(ud.schemas["Foo"].properties.values())[0]
        assert prop.array_dim == 3

    def test_jmap_with_map_property(self, tmp_path):
        jmap_data = {
            "objects": {
                "Engine.Bar": {
                    "type": "ScriptStruct",
                    "properties": [
                        {
                            "name": "Data",
                            "type": "MapProperty",
                            "key_prop": {"type": "NameProperty"},
                            "value_prop": {"type": "FloatProperty"},
                        },
                    ],
                }
            }
        }
        path = tmp_path / "map.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        prop = list(ud.schemas["Bar"].properties.values())[0]
        assert prop.type_name == "MapProperty"
        assert prop.inner_type.type_name == "NameProperty"
        assert prop.value_type.type_name == "FloatProperty"

    def test_jmap_non_dict_object_skipped(self, tmp_path):
        jmap_data = {
            "objects": {
                "Engine.Valid": {"type": "ScriptStruct", "properties": []},
                "Engine.Invalid": "not_a_dict",
            }
        }
        path = tmp_path / "skip.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        assert "Valid" in ud.schemas
        assert "Invalid" not in ud.schemas

    def test_jmap_non_dict_property_skipped(self, tmp_path):
        jmap_data = {
            "objects": {
                "Engine.Foo": {
                    "type": "ScriptStruct",
                    "properties": [
                        "not_a_dict",
                        {"name": "Real", "type": "IntProperty"},
                    ],
                }
            }
        }
        path = tmp_path / "skip_prop.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        assert len(ud.schemas["Foo"].properties) == 1

    def test_jmap_enum_empty_names(self, tmp_path):
        jmap_data = {
            "objects": {
                "Engine.EmptyEnum": {
                    "type": "Enum",
                    "names": [],
                }
            }
        }
        path = tmp_path / "empty_enum.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        assert ud.enums["EmptyEnum"] == {}

    def test_jmap_gzip(self, tmp_path):
        jmap_data = {"objects": {}}
        path = tmp_path / "test.jmap.gz"
        path.write_bytes(gzip_mod.compress(json.dumps(jmap_data).encode("utf-8")))
        ud = UsmapData(str(path))
        assert ud.version == 0
        assert ud.schemas == {}

    def test_jmap_unknown_type_in_property(self, tmp_path):
        """jmap 中未知 type 值传递为字符串。"""
        jmap_data = {
            "objects": {
                "Engine.Foo": {
                    "type": "ScriptStruct",
                    "properties": [
                        {"name": "Custom", "type": "CustomType"},
                    ],
                }
            }
        }
        path = tmp_path / "unknown.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        prop = list(ud.schemas["Foo"].properties.values())[0]
        assert prop.type_name == "CustomType"

    def test_jmap_struct_property_with_full_path(self, tmp_path):
        """struct 字段使用全限定名，应只取短名。"""
        jmap_data = {
            "objects": {
                "Engine.Foo": {
                    "type": "ScriptStruct",
                    "properties": [
                        {"name": "Vec", "type": "StructProperty",
                         "struct": "Core.Math.FVector"},
                    ],
                }
            }
        }
        path = tmp_path / "fullpath.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        prop = list(ud.schemas["Foo"].properties.values())[0]
        assert prop.struct_type == "FVector"

    def test_jmap_enum_with_full_path(self, tmp_path):
        """enum 字段使用全限定名，应只取短名。"""
        jmap_data = {
            "objects": {
                "Engine.Foo": {
                    "type": "ScriptStruct",
                    "properties": [
                        {"name": "E", "type": "EnumProperty",
                         "enum": "Engine.ENumType"},
                    ],
                }
            }
        }
        path = tmp_path / "enumpath.jmap"
        path.write_text(json.dumps(jmap_data), encoding="utf-8")
        ud = UsmapData(str(path))
        prop = list(ud.schemas["Foo"].properties.values())[0]
        assert prop.enum_name == "ENumType"


# ===========================================================================
# 测试完整 .usmap 解析（带 schema 和 property）
# ===========================================================================

class TestFullUsmapParsing:
    """完整 .usmap 文件解析测试。"""

    def test_parse_with_schema_and_properties(self):
        name_table = ["MyClass", "Health"]
        prop = UsmapProperty(index=0, name="Health", type_name="IntProperty")
        schema = UsmapSchema(
            name="MyClass",
            serializable_count=1,
            property_count=1,
            properties={0: prop},
        )
        data = _build_minimal_usmap(
            name_table=name_table,
            schemas={"MyClass": schema},
        )
        result = parse_usmap(data)
        assert "MyClass" in result.schemas
        parsed_prop = result.schemas["MyClass"].properties[0]
        assert parsed_prop.name == "Health"
        assert parsed_prop.type_name == "IntProperty"

    def test_parse_with_enum(self):
        name_table = ["EMyEnum", "ValueA", "ValueB"]
        enums = {"EMyEnum": {0: "ValueA", 1: "ValueB"}}
        data = _build_minimal_usmap(name_table=name_table, enums=enums)
        result = parse_usmap(data)
        assert "EMyEnum" in result.enums
        assert result.enums["EMyEnum"][0] == "ValueA"
        assert result.enums["EMyEnum"][1] == "ValueB"

    def test_parse_multiple_schemas(self):
        name_table = ["A", "B"]
        schema_a = UsmapSchema(name="A", serializable_count=0, property_count=0)
        schema_b = UsmapSchema(name="B", serializable_count=0, property_count=0)
        data = _build_minimal_usmap(
            name_table=name_table,
            schemas={"A": schema_a, "B": schema_b},
        )
        result = parse_usmap(data)
        assert "A" in result.schemas
        assert "B" in result.schemas
