"""serialization 模块合并测试 — 覆盖核心序列化与恢复场景。

保留 4 个关键用例：
1. 序列化策略枚举与策略表
2. ClassHandlerRegistry 注册与查找
3. PropertyTag 损坏 strict/tolerant 行为
4. BinaryOrNative 处理器（FMaterialInput）
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, List, Optional
from unittest.mock import MagicMock

import pytest

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError
from uasset_read.parsers.binary_or_native_handlers import (
    BINARY_OR_NATIVE_HANDLERS,
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
    should_skip_class,
    is_opaque_class,
)
from uasset_read.parsers.asset_types import register_asset_type_handlers
from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex

from conftest import FakeArchive


# ============================================================================
# 辅助工厂
# ============================================================================

def _make_archive(data: bytes, tolerant: bool = False, file_version_ue5: int = 1012) -> FArchive:
    """从原始字节创建 FArchive 实例（用于测试）。"""
    archive = FArchive.__new__(FArchive)
    archive._stream = BytesIO(data)
    archive._file_size = len(data)
    archive._byte_swapping = False
    archive._use_mmap = False
    archive._mmap = None
    archive._tolerant = tolerant
    archive._file = BytesIO(data)
    archive._hex_view_enabled = False
    archive._hex_view_entries = []
    archive._hex_view_context = ""
    archive._diagnostics = []
    archive._logger = __import__("logging").getLogger("test")
    archive._name_map = None
    archive._file_version_ue5 = file_version_ue5
    return archive


def _make_export(serial_offset: int = 0, serial_size: int = 1024) -> ObjectExport:
    """创建测试用 ObjectExport。"""
    return ObjectExport(
        class_index=PackageIndex(-1),
        super_index=PackageIndex(-1),
        outer_index=PackageIndex(0),
        object_name="TestExport",
        object_flags=0,
        serial_size=serial_size,
        serial_offset=serial_offset,
    )


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
    serialize_type: str = "BinaryOrNative"
    type_name: Any = None


# ============================================================================
# 用例 1: 序列化策略枚举与策略表
# ============================================================================

class TestSerializationStrategy:
    """SerializationStrategy 枚举与 CLASS_STRATEGY_TABLE 测试。"""

    def test_enum_values_and_strategy_table(self):
        """枚举值正确定义，策略表映射正确。"""
        # 枚举值
        assert SerializationStrategy.TAGGED_PROPERTIES_ONLY.value == "tagged_properties_only"
        assert SerializationStrategy.OPAQUE_CLASS_PAYLOAD.value == "opaque_class_payload"
        assert SerializationStrategy.SKIP_UNSUPPORTED.value == "skip_unsupported"

        # Tagged properties 类
        for cls in ["BlueprintGeneratedClass", "Function", "EdGraph"]:
            assert CLASS_STRATEGY_TABLE[cls] == SerializationStrategy.TAGGED_PROPERTIES_ONLY

        # Opaque payload 类
        for cls in ["StaticMesh", "Texture2D", "Material", "AnimSequence"]:
            assert CLASS_STRATEGY_TABLE[cls] == SerializationStrategy.OPAQUE_CLASS_PAYLOAD

        # 未知类默认返回 TAGGED_PROPERTIES_ONLY
        assert get_serialization_strategy("UnknownCustomClass") == SerializationStrategy.TAGGED_PROPERTIES_ONLY

        # 三个类别无重叠
        tagged = {c for c, s in CLASS_STRATEGY_TABLE.items() if s == SerializationStrategy.TAGGED_PROPERTIES_ONLY}
        opaque = {c for c, s in CLASS_STRATEGY_TABLE.items() if s == SerializationStrategy.OPAQUE_CLASS_PAYLOAD}
        skip = {c for c, s in CLASS_STRATEGY_TABLE.items() if s == SerializationStrategy.SKIP_UNSUPPORTED}
        assert len(tagged & opaque) == 0
        assert len(tagged & skip) == 0
        assert len(opaque & skip) == 0


# ============================================================================
# 用例 2: ClassHandlerRegistry 注册与查找
# ============================================================================

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


class TestClassHandlerRegistry:
    """ClassHandlerRegistry 注册与查找测试。"""

    def test_registry_register_and_lookup(self):
        """注册->查找->未注册返回 None->缓存命中。"""
        reg = ClassHandlerRegistry()
        handler = _MockHandler("TestHandler", ["MyClass"])
        reg.register(handler)
        found = reg.find_handler("MyClass")
        assert found is not None and found.handler_name == "TestHandler"
        assert reg.find_handler("UnknownClass") is None
        assert reg.find_handler("MyClass") is reg.find_handler("MyClass")


# ============================================================================
# 用例 3: PropertyTag 损坏 strict/tolerant 行为
# ============================================================================

class TestCorruptedTagBehavior:
    """损坏 tag 在 strict/tolerant 模式下的行为。"""

    def test_strict_raises_on_truncated_tag(self):
        """strict 模式下 tag 名称截断应抛出 ParseError。"""
        name_bytes = struct.pack("<II", 0, 0)
        truncated_bytes = b"\x00" * 2
        data = name_bytes + truncated_bytes
        archive = _make_archive(data, tolerant=False)
        archive._file_version_ue5 = 1012
        summary = MagicMock()
        summary.package_flags = 0
        summary.file_version_ue5 = 1012
        export = _make_export(serial_offset=0, serial_size=100)
        with pytest.raises(ParseError):
            parse_properties_from_export(
                export, archive, summary,
                name_map=["TestProp"], export_map=[], tolerant=False,
            )

    def test_tolerant_does_not_hang_on_truncated_tag(self):
        """tolerant 模式下 tag 截断不应挂起。"""
        name_bytes = struct.pack("<II", 0, 0)
        truncated_bytes = b"\x00" * 2
        data = name_bytes + truncated_bytes
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1012
        summary = MagicMock()
        summary.package_flags = 0
        summary.file_version_ue5 = 1012
        export = _make_export(serial_offset=0, serial_size=100)
        result = parse_properties_from_export(
            export, archive, summary,
            name_map=["TestProp"], export_map=[], tolerant=True,
        )
        assert isinstance(result, list)
        assert len(result) >= 1


# ============================================================================
# 用例 4: BinaryOrNative 处理器（FMaterialInput）
# ============================================================================

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


# ============================================================================
# 用例 5: Opaque handler 注册（合并自 test_unit.py）
# ============================================================================

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
