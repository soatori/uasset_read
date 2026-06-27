"""BinaryOrNative 类型处理器测试。

覆盖 _parse_material_input、_parse_expression_output、_parse_instanced_struct
三个核心解析函数的成功路径和边界条件。
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass, field
from typing import Any, List, Optional
from unittest.mock import MagicMock

import pytest

from uasset_read.parsers.binary_or_native_handlers import (
    BINARY_OR_NATIVE_HANDLERS,
    _parse_expression_output,
    _parse_instanced_struct,
    _parse_material_input,
)


# ---------------------------------------------------------------------------
# 测试用模拟对象
# ---------------------------------------------------------------------------

@dataclass
class FakePropertyTag:
    """模拟 PropertyTag，仅保留解析所需字段。"""
    name: str = ""
    type: str = "BinaryOrNative"
    size: int = 0
    array_index: int = 0
    flags: int = 0
    property_guid: Optional[bytes] = None
    bool_val: int = 0
    override_operation: Optional[int] = None
    experimental_overridable_logic: Optional[int] = None
    serialize_type: str = "BinaryOrNative"
    type_name: Any = None
    tag_data: Any = None
    enum_type: Optional[str] = None
    type_parts: List = field(default_factory=list)


class FakeArchive:
    """基于 BytesIO 的轻量 FArchive 模拟，支持 read_i32 / read_name / tell / seek。"""

    def __init__(self, data: bytes) -> None:
        self._buf = io.BytesIO(data)
        self._byte_swapping = False

    def read(self, size: int) -> bytes:
        return self._buf.read(size)

    def read_i32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def read_name(self, name_map: Optional[List[str]] = None) -> str:
        # 简化 FName：仅读取 int32 索引作为名称
        idx = self.read_i32()
        if name_map and 0 <= idx < len(name_map):
            return name_map[idx]
        return f"Name_{idx}"

    def tell(self) -> int:
        return self._buf.tell()

    def seek(self, pos: int) -> None:
        self._buf.seek(pos)


def _build_material_input_data(
    output_index: int = 0,
    input_name_idx: int = 1,
    mask: int = 0xFF,
    mask_r: int = 1,
    mask_g: int = 2,
    mask_b: int = 3,
    mask_a: int = 4,
) -> bytes:
    """构造 FMaterialInput 二进制数据。"""
    buf = io.BytesIO()
    buf.write(struct.pack("<i", output_index))
    buf.write(struct.pack("<i", input_name_idx))
    buf.write(struct.pack("<i", mask))
    buf.write(struct.pack("<i", mask_r))
    buf.write(struct.pack("<i", mask_g))
    buf.write(struct.pack("<i", mask_b))
    buf.write(struct.pack("<i", mask_a))
    return buf.getvalue()


def _build_expression_output_data(
    output_name_idx: int = 2,
    mask: int = 0xF0,
    mask_r: int = 10,
    mask_g: int = 20,
    mask_b: int = 30,
    mask_a: int = 40,
) -> bytes:
    """构造 FExpressionOutput 二进制数据。"""
    buf = io.BytesIO()
    buf.write(struct.pack("<i", output_name_idx))
    buf.write(struct.pack("<i", mask))
    buf.write(struct.pack("<i", mask_r))
    buf.write(struct.pack("<i", mask_g))
    buf.write(struct.pack("<i", mask_b))
    buf.write(struct.pack("<i", mask_a))
    return buf.getvalue()


def _build_instanced_struct_data(
    script_struct_index: int = 42,
    extra_data: bytes = b"",
) -> bytes:
    """构造 FInstancedStruct 二进制数据。"""
    buf = io.BytesIO()
    buf.write(struct.pack("<i", script_struct_index))
    buf.write(extra_data)
    return buf.getvalue()


# ===========================================================================
# TestMaterialInput
# ===========================================================================

class TestMaterialInput:
    """材质输入（FMaterialInput）解析测试。"""

    def test_parse_material_input_success(self):
        """正常解析完整 FMaterialInput 数据，字段一一对应。"""
        data = _build_material_input_data(
            output_index=3,
            input_name_idx=0,
            mask=0xFF,
            mask_r=1, mask_g=2, mask_b=3, mask_a=4,
        )
        tag = FakePropertyTag(type="FVectorMaterialInput", size=len(data))
        name_map = ["BaseColor"]
        archive = FakeArchive(data)

        result = _parse_material_input(tag, archive, name_map, [], None)

        assert result is not None
        assert result["kind"] == "material_input"
        assert result["type"] == "FVectorMaterialInput"
        assert result["size"] == len(data)
        assert result["output_index"] == 3
        assert result["input_name"] == "BaseColor"
        assert result["mask"] == 0xFF
        assert result["mask_r"] == 1
        assert result["mask_g"] == 2
        assert result["mask_b"] == 3
        assert result["mask_a"] == 4

    def test_parse_material_input_all_variants(self):
        """所有 FMaterialInput 变体类型均注册到处理器表。"""
        variants = [
            "FMaterialInput",
            "FColorMaterialInput",
            "FScalarMaterialInput",
            "FVectorMaterialInput",
            "FVector2MaterialInput",
        ]
        for variant in variants:
            assert variant in BINARY_OR_NATIVE_HANDLERS
            assert BINARY_OR_NATIVE_HANDLERS[variant] is _parse_material_input

    def test_parse_material_input_insufficient_size(self):
        """数据不足 28 字节时返回 None，不移动游标。"""
        # size = 27（少 1 字节）
        data = b"\x00" * 27
        tag = FakePropertyTag(type="FMaterialInput", size=27)
        archive = FakeArchive(b"\x00" * 64)
        pos_before = archive.tell()

        result = _parse_material_input(tag, archive, [], [], None)

        assert result is None
        assert archive.tell() == pos_before

    def test_parse_material_input_empty_data(self):
        """size = 0 时返回 None。"""
        tag = FakePropertyTag(type="FMaterialInput", size=0)
        archive = FakeArchive(b"\x00" * 8)

        result = _parse_material_input(tag, archive, [], [], None)

        assert result is None

    def test_parse_material_input_exact_min_size(self):
        """恰好 28 字节可以正常解析。"""
        data = _build_material_input_data()
        assert len(data) == 28

        tag = FakePropertyTag(type="FScalarMaterialInput", size=28)
        archive = FakeArchive(data)

        result = _parse_material_input(tag, archive, [], [], None)

        assert result is not None
        assert result["output_index"] == 0
        assert result["kind"] == "material_input"

    def test_parse_material_input_archive_exception(self):
        """read 异常时回退到 None，游标恢复到起始位置。"""
        tag = FakePropertyTag(type="FMaterialInput", size=28)
        # 空 archive，read 会失败
        archive = FakeArchive(b"")
        pos_before = archive.tell()

        result = _parse_material_input(tag, archive, [], [], None)

        assert result is None
        assert archive.tell() == pos_before


# ===========================================================================
# TestExpressionOutput
# ===========================================================================

class TestExpressionOutput:
    """表达式输出（FExpressionOutput）解析测试。"""

    def test_parse_expression_output_success(self):
        """正常解析完整 FExpressionOutput 数据，字段一一对应。"""
        data = _build_expression_output_data(
            output_name_idx=5,
            mask=0xAB,
            mask_r=11, mask_g=22, mask_b=33, mask_a=44,
        )
        tag = FakePropertyTag(type="FExpressionOutput", size=len(data))
        name_map = ["", "", "", "", "", "EmissiveColor"]
        archive = FakeArchive(data)

        result = _parse_expression_output(tag, archive, name_map, [], None)

        assert result is not None
        assert result["kind"] == "expression_output"
        assert result["type"] == "FExpressionOutput"
        assert result["size"] == len(data)
        assert result["output_name"] == "EmissiveColor"
        assert result["mask"] == 0xAB
        assert result["mask_r"] == 11
        assert result["mask_g"] == 22
        assert result["mask_b"] == 33
        assert result["mask_a"] == 44

    def test_parse_expression_output_insufficient_size(self):
        """数据不足 24 字节时返回 None。"""
        data = b"\x00" * 23
        tag = FakePropertyTag(type="FExpressionOutput", size=23)
        archive = FakeArchive(b"\x00" * 64)
        pos_before = archive.tell()

        result = _parse_expression_output(tag, archive, [], [], None)

        assert result is None
        assert archive.tell() == pos_before

    def test_parse_expression_output_empty_data(self):
        """size = 0 时返回 None。"""
        tag = FakePropertyTag(type="FExpressionOutput", size=0)
        archive = FakeArchive(b"\x00" * 8)

        result = _parse_expression_output(tag, archive, [], [], None)

        assert result is None

    def test_parse_expression_output_exact_min_size(self):
        """恰好 24 字节可以正常解析。"""
        data = _build_expression_output_data()
        assert len(data) == 24

        tag = FakePropertyTag(type="FExpressionOutput", size=24)
        archive = FakeArchive(data)

        result = _parse_expression_output(tag, archive, [], [], None)

        assert result is not None
        assert result["kind"] == "expression_output"

    def test_parse_expression_output_archive_exception(self):
        """read 异常时回退到 None，游标恢复到起始位置。"""
        tag = FakePropertyTag(type="FExpressionOutput", size=24)
        archive = FakeArchive(b"\x00\x01")  # 数据不足但 size 声称 24
        pos_before = archive.tell()

        result = _parse_expression_output(tag, archive, [], [], None)

        assert result is None
        assert archive.tell() == pos_before

    def test_parse_expression_output_no_name_map(self):
        """name_map 为空列表时，仍能正常解析（使用索引数字作为名称）。"""
        data = _build_expression_output_data(output_name_idx=0)
        tag = FakePropertyTag(type="FExpressionOutput", size=len(data))
        archive = FakeArchive(data)

        result = _parse_expression_output(tag, archive, [], [], None)

        assert result is not None
        assert result["output_name"] == "Name_0"


# ===========================================================================
# TestInstancedStruct
# ===========================================================================

class TestInstancedStruct:
    """实例化结构体（FInstancedStruct）解析测试。"""

    def test_parse_instanced_struct_success(self):
        """正常解析带额外数据的 FInstancedStruct。"""
        extra = b"\xDE\xAD\xBE\xEF"
        data = _build_instanced_struct_data(script_struct_index=7, extra_data=extra)
        tag = FakePropertyTag(type="FInstancedStruct", size=len(data))
        archive = FakeArchive(data)

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is not None
        assert result["kind"] == "instanced_struct"
        assert result["type"] == "FInstancedStruct"
        assert result["size"] == len(data)
        assert result["script_struct_index"] == 7
        assert result["struct_data"] == extra

    def test_parse_instanced_struct_no_extra_data(self):
        """仅有 ScriptStruct 索引（无额外数据）时 struct_data 为空字节。"""
        data = _build_instanced_struct_data(script_struct_index=0, extra_data=b"")
        tag = FakePropertyTag(type="FInstancedStruct", size=4)
        archive = FakeArchive(data)

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is not None
        assert result["script_struct_index"] == 0
        assert result["struct_data"] == b""

    def test_parse_instanced_struct_insufficient_size(self):
        """数据不足 4 字节时返回 None。"""
        tag = FakePropertyTag(type="FInstancedStruct", size=3)
        archive = FakeArchive(b"\x00\x00\x00")
        pos_before = archive.tell()

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is None
        assert archive.tell() == pos_before

    def test_parse_instanced_struct_empty_data(self):
        """size = 0 时返回 None。"""
        tag = FakePropertyTag(type="FInstancedStruct", size=0)
        archive = FakeArchive(b"\x00" * 16)

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is None

    def test_parse_instanced_struct_exact_min_size(self):
        """恰好 4 字节（仅索引，无 struct_data）可以正常解析。"""
        data = struct.pack("<i", 99)
        tag = FakePropertyTag(type="FInstancedStruct", size=4)
        archive = FakeArchive(data)

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is not None
        assert result["script_struct_index"] == 99
        assert result["struct_data"] == b""

    def test_parse_instanced_struct_large_extra(self):
        """大量额外数据完整保留。"""
        extra = bytes(range(256)) * 4  # 1024 字节
        data = _build_instanced_struct_data(script_struct_index=1, extra_data=extra)
        tag = FakePropertyTag(type="FInstancedStruct", size=len(data))
        archive = FakeArchive(data)

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is not None
        assert result["struct_data"] == extra
        assert len(result["struct_data"]) == 1024

    def test_parse_instanced_struct_archive_exception(self):
        """read 异常时回退到 None，游标恢复到起始位置。"""
        tag = FakePropertyTag(type="FInstancedStruct", size=20)
        archive = FakeArchive(b"\x00\x01")  # 只有 2 字节
        pos_before = archive.tell()

        result = _parse_instanced_struct(tag, archive, [], [], None)

        assert result is None
        assert archive.tell() == pos_before


# ===========================================================================
# 处理器注册表完整性
# ===========================================================================

class TestHandlerRegistry:
    """验证 BINARY_OR_NATIVE_HANDLERS 注册表结构。"""

    def test_all_handlers_registered(self):
        """注册表包含所有预期的类型键。"""
        expected_keys = {
            "FMaterialInput",
            "FColorMaterialInput",
            "FScalarMaterialInput",
            "FVectorMaterialInput",
            "FVector2MaterialInput",
            "FExpressionOutput",
            "FInstancedStruct",
            "StructProperty",  # #143: 二进制 StructProperty 解码
        }
        assert set(BINARY_OR_NATIVE_HANDLERS.keys()) == expected_keys

    def test_all_handlers_are_callable(self):
        """每个注册的处理器都是可调用对象。"""
        for name, handler in BINARY_OR_NATIVE_HANDLERS.items():
            assert callable(handler), f"{name} 不可调用"
