"""serialization 模块测试 — 策略枚举、ClassHandlerRegistry、MaterialInput。"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from uasset_read.parsers.binary_or_native_handlers import (
    _parse_material_input,
)
from uasset_read.parsers.class_registry import (
    ClassHandlerRegistry,
    ClassHandler,
    HandlerResult,
    FallbackPolicy,
    get_class_registry,
    reset_class_registry,
)
from uasset_read.parsers.class_serialization_strategy import (
    SerializationStrategy,
    CLASS_STRATEGY_TABLE,
    get_serialization_strategy,
)
from uasset_read.parsers.asset_types import register_asset_type_handlers


class FakeArchive:
    """BytesIO 的轻量 FArchive 模拟。"""
    def __init__(self, data: bytes | None = None):
        self._buf = io.BytesIO(data) if data else io.BytesIO()

    def read(self, size: int) -> bytes:
        return self._buf.read(size)

    def read_i32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def read_i64(self) -> int:
        return struct.unpack("<q", self.read(8))[0]

    def read_u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def read_fstring(self) -> str:
        length = self.read_i32()
        if length == 0:
            return ""
        if length > 0:
            raw = self.read(length)
            return raw[:-1].decode("utf-8") if raw.endswith(b"\x00") else raw.decode("utf-8")
        byte_count = -length * 2
        raw = self.read(byte_count)
        return raw[:-2].decode("utf-16-le") if raw.endswith(b"\x00\x00") else raw.decode("utf-16-le")

    def read_name(self, name_map: list[str]) -> str:
        index = self.read_u32()
        self.read_u32()  # number
        if 0 <= index < len(name_map):
            return name_map[index]
        return "None"

    def tell(self) -> int:
        return self._buf.tell()

    def seek(self, pos: int) -> None:
        self._buf.seek(pos)

    def total_size(self) -> int:
        current = self._buf.tell()
        self._buf.seek(0, 2)
        size = self._buf.tell()
        self._buf.seek(current)
        return size


@dataclass
class FakePropertyTag:
    """模拟 PropertyTag。"""
    name: str = ""
    type: str = "BinaryOrNative"
    size: int = 0
    array_index: int = 0
    flags: int = 0
    property_guid: Optional[bytes] = None
    bool_val: int = 0
    serialize_type: str = "BinaryOrNative"
    type_name: Any = None


class _MockHandler(ClassHandler):
    """测试用 mock handler。"""
    def __init__(self, name: str, can_handle_names: list[str]):
        self._name = name
        self._can_handle = set(can_handle_names)
    def can_handle(self, class_name: str) -> bool:
        return class_name in self._can_handle
    @property
    def handler_name(self) -> str:
        return self._name
    @property
    def fallback_policy(self) -> FallbackPolicy:
        return FallbackPolicy.GENERIC_UOBJECT
    def parse(self, export, archive, context) -> HandlerResult:
        return HandlerResult(success=True, properties=[], data={"handled_by": self._name})


class TestSerializationStrategy:
    """SerializationStrategy 枚举与策略表。"""

    def test_enum_values_and_strategy_table(self):
        """枚举值正确定义，策略表映射正确。"""
        assert SerializationStrategy.TAGGED_PROPERTIES_ONLY.value == "tagged_properties_only"
        assert SerializationStrategy.OPAQUE_CLASS_PAYLOAD.value == "opaque_class_payload"
        assert SerializationStrategy.SKIP_UNSUPPORTED.value == "skip_unsupported"

        for cls in ["BlueprintGeneratedClass", "Function", "EdGraph"]:
            assert CLASS_STRATEGY_TABLE[cls] == SerializationStrategy.TAGGED_PROPERTIES_ONLY

        for cls in ["StaticMesh", "Texture2D", "Material", "AnimSequence"]:
            assert CLASS_STRATEGY_TABLE[cls] == SerializationStrategy.OPAQUE_CLASS_PAYLOAD

        assert get_serialization_strategy("UnknownCustomClass") == SerializationStrategy.TAGGED_PROPERTIES_ONLY

        tagged = {c for c, s in CLASS_STRATEGY_TABLE.items() if s == SerializationStrategy.TAGGED_PROPERTIES_ONLY}
        opaque = {c for c, s in CLASS_STRATEGY_TABLE.items() if s == SerializationStrategy.OPAQUE_CLASS_PAYLOAD}
        skip = {c for c, s in CLASS_STRATEGY_TABLE.items() if s == SerializationStrategy.SKIP_UNSUPPORTED}
        assert len(tagged & opaque) == 0
        assert len(tagged & skip) == 0
        assert len(opaque & skip) == 0


class TestClassHandlerRegistry:
    """ClassHandlerRegistry 注册与查找。"""

    def test_registry_register_and_lookup(self):
        """注册->查找->未注册返回 None->缓存命中。"""
        reg = ClassHandlerRegistry()
        handler = _MockHandler("TestHandler", ["MyClass"])
        reg.register(handler)
        found = reg.find_handler("MyClass")
        assert found is not None and found.handler_name == "TestHandler"
        assert reg.find_handler("UnknownClass") is None
        assert reg.find_handler("MyClass") is reg.find_handler("MyClass")


def _build_material_input_data(
    output_index: int = 0,
    input_name_idx: int = 1,
    mask: int = 0xFF,
    mask_r: int = 1, mask_g: int = 2, mask_b: int = 3, mask_a: int = 4,
) -> bytes:
    """构造 FMaterialInput 二进制数据。"""
    buf = io.BytesIO()
    buf.write(struct.pack("<i", output_index))
    buf.write(struct.pack("<i", input_name_idx))
    buf.write(struct.pack("<i", 0))
    buf.write(struct.pack("<i", mask))
    buf.write(struct.pack("<i", mask_r))
    buf.write(struct.pack("<i", mask_g))
    buf.write(struct.pack("<i", mask_b))
    buf.write(struct.pack("<i", mask_a))
    return buf.getvalue()


class TestMaterialInput:
    """FMaterialInput 解析测试。"""

    def test_parse_material_input_success(self):
        """正常解析完整 FMaterialInput 数据。"""
        data = _build_material_input_data(output_index=3, input_name_idx=0)
        tag = FakePropertyTag(type="FVectorMaterialInput", size=len(data))
        name_map = ["BaseColor"]
        archive = FakeArchive(data)
        result = _parse_material_input(tag, archive, name_map, [], None)
        assert result is not None
        assert result["kind"] == "material_input"
        assert result["output_index"] == 3
        assert result["input_name"] == "BaseColor"

    def test_parse_material_input_insufficient_size(self):
        """数据不足时返回 None，不移动游标。"""
        data = b"\x00" * 27
        tag = FakePropertyTag(type="FMaterialInput", size=27)
        archive = FakeArchive(b"\x00" * 64)
        pos_before = archive.tell()
        result = _parse_material_input(tag, archive, [], [], None)
        assert result is None
        assert archive.tell() == pos_before


@pytest.fixture()
def _fresh_registry():
    """重置 class_registry 并注册默认 handler。"""
    reset_class_registry()
    register_asset_type_handlers()
    yield
    reset_class_registry()


@pytest.mark.usefixtures("_fresh_registry")
class TestOpaqueHandlers:
    def test_handler_registered_foliage(self):
        """FoliageType 应有注册的 handler。"""
        registry = get_class_registry()
        handler = registry.find_handler("FoliageType")
        assert handler is not None
