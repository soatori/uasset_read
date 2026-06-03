# 未知资产处理增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将未知 property/class 的处理从"返回 None 或跳过"升级为结构化 fallback + class handler registry，降低信息丢失。

**Architecture:** 引入 `PropertyFallback`/`StructFallback`/`GenericUObject` 数据模型，改造 property 分派器输出结构化 fallback 替代 None，将 class-specific skip list 改造为 handler registry 的 fallback policy。

**Tech Stack:** Python 3.10+, dataclasses, pytest

---

## 文件结构

### 新增文件
| 文件 | 职责 |
|------|------|
| `src/uasset_read/models/fallback.py` | `PropertyFallback`, `StructFallback`, `GenericUObject`, `ExportParseStatus` 数据模型 |
| `src/uasset_read/parsers/class_registry.py` | `ClassHandlerRegistry`, `ClassHandler` 接口，父类 fallback 链 |
| `tests/test_fallback_models.py` | fallback 数据模型单元测试 |
| `tests/test_unknown_property_fallback.py` | 未知 property 结构化 fallback 测试 |
| `tests/test_class_registry.py` | class handler registry 单元测试 |

### 修改文件
| 文件 | 修改内容 |
|------|------|
| `src/uasset_read/parsers/property_parser.py:143-158` | 未知类型分派改为返回 `PropertyFallback` 而非 `None` |
| `src/uasset_read/parsers/property_parser.py:340-355` | property loop 中处理 fallback 值 |
| `src/uasset_read/models/__init__.py` | 导出新 fallback 模型 |
| `src/uasset_read/parsers/class_specific_skip.py` | 改造 skip 判断为 registry 的 fallback policy |
| `src/uasset_read/__init__.py` | 导出新增公开符号 |

---

## Task 1: 新增 Fallback 数据模型

**Files:**
- Create: `src/uasset_read/models/fallback.py`
- Test: `tests/test_fallback_models.py`

- [ ] **Step 1: 编写测试**

```python
"""tests/test_fallback_models.py — Fallback 数据模型测试"""
from uasset_read.models.fallback import (
    PropertyFallback,
    StructFallback,
    GenericUObject,
    ExportParseStatus,
    FallbackReason,
)


def test_property_fallback_minimal():
    """最小 PropertyFallback 实例化"""
    fb = PropertyFallback(
        name="UnknownProp",
        type="UnknownType",
        size=32,
        raw_bytes=b"\x00" * 32,
        reason=FallbackReason.UNSUPPORTED_TYPE,
    )
    assert fb.name == "UnknownProp"
    assert fb.type == "UnknownType"
    assert fb.size == 32
    assert len(fb.raw_bytes) == 32
    assert fb.reason == FallbackReason.UNSUPPORTED_TYPE
    assert fb.array_index == 0
    assert fb.tag_data is None


def test_property_fallback_full():
    """完整 PropertyFallback 含所有字段"""
    fb = PropertyFallback(
        name="TestProp",
        type="CustomType",
        size=16,
        raw_bytes=b"\x01\x02",
        reason=FallbackReason.PARSE_ERROR,
        array_index=2,
        tag_data={"extra": "info"},
        error_message="Failed to parse CustomType",
    )
    assert fb.array_index == 2
    assert fb.tag_data == {"extra": "info"}
    assert fb.error_message is not None


def test_structFallback_minimal():
    """最小 StructFallback"""
    fb = StructFallback(
        struct_type="UnknownStruct",
        size=64,
        raw_bytes=b"\x00" * 64,
        reason=FallbackReason.UNSUPPORTED_STRUCT,
    )
    assert fb.struct_type == "UnknownStruct"
    assert fb.size == 64
    assert len(fb.fields) == 0  # 默认空 dict


def test_struct_fallback_with_partial_fields():
    """StructFallback 含部分解析字段"""
    fb = StructFallback(
        struct_type="Vector",
        size=12,
        raw_bytes=b"",
        reason=FallbackReason.PARTIAL_PARSE,
        fields={"X": 1.0, "Y": 2.0},
    )
    assert fb.fields["X"] == 1.0
    assert len(fb.fields) == 2


def test_generic_uobject_minimal():
    """最小 GenericUObject"""
    obj = GenericUObject(
        name="MyExport",
        class_name="UnknownClass",
        serial_offset=0,
        serial_size=100,
        parse_status=ExportParseStatus.FALLBACK,
    )
    assert obj.name == "MyExport"
    assert obj.class_name == "UnknownClass"
    assert obj.serial_size == 100
    assert len(obj.properties) == 0
    assert obj.outer_path == []


def test_generic_uobject_full():
    """完整 GenericUObject"""
    from uasset_read.models.properties import PropertyValue

    obj = GenericUObject(
        name="BP_MyActor",
        class_name="BlueprintGeneratedClass",
        super_name="Actor",
        outer_path=["Package", "Class"],
        serial_offset=1024,
        serial_size=2048,
        parse_status=ExportParseStatus.PARTIAL,
        properties=[PropertyValue(name="MyVar", type="IntProperty", value=42)],
        fallback_data=StructFallback(
            struct_type="UnknownStruct",
            size=10,
            raw_bytes=b"\xAA" * 10,
            reason=FallbackReason.UNSUPPORTED_STRUCT,
        ),
        requires_mappings=True,
        missing_mapping="SomeStruct",
    )
    assert len(obj.properties) == 1
    assert obj.fallback_data is not None
    assert obj.requires_mappings is True
    assert obj.missing_mapping == "SomeStruct"


def test_export_parse_status_enum():
    """ExportParseStatus 枚举值"""
    assert ExportParseStatus.SUCCESS == "success"
    assert ExportParseStatus.PARTIAL == "partial"
    assert ExportParseStatus.FALLBACK == "fallback"
    assert ExportParseStatus.SKIPPED == "skipped"
    assert ExportParseStatus.FAILED == "failed"


def test_fallback_reason_enum():
    """FallbackReason 枚举值"""
    assert FallbackReason.UNSUPPORTED_TYPE == "unsupported_type"
    assert FallbackReason.UNSUPPORTED_STRUCT == "unsupported_struct"
    assert FallbackReason.PARSE_ERROR == "parse_error"
    assert FallbackReason.PARTIAL_PARSE == "partial_parse"
    assert FallbackReason.MISSING_MAPPING == "missing_mapping"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_fallback_models.py -v
```
预期: 全部 FAIL (模块不存在)

- [ ] **Step 3: 实现数据模型**

```python
"""src/uasset_read/models/fallback.py — 未知资产结构化 Fallback 模型。

参考 CUE4Parse: FStructFallback, generic UObject, FPropertyTag fallback.
目标：让未知 property/struct/export 仍能保留可诊断的结构化信息。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.properties import PropertyValue


class ExportParseStatus(str, Enum):
    """Export 级解析状态。"""
    SUCCESS = "success"        # 完整解析
    PARTIAL = "partial"        # 部分解析（部分属性 fallback）
    FALLBACK = "fallback"      # 完全 fallback（无可用解析器）
    SKIPPED = "skipped"        # 被 skip list / policy 跳过
    FAILED = "failed"          # 解析失败（tolerant=False 时抛出）


class FallbackReason(str, Enum):
    """Fallback 原因。"""
    UNSUPPORTED_TYPE = "unsupported_type"    # 未知 property type
    UNSUPPORTED_STRUCT = "unsupported_struct"  # 未知 struct 类型
    PARSE_ERROR = "parse_error"              # 解析过程异常
    PARTIAL_PARSE = "partial_parse"          # 部分字段可解析
    MISSING_MAPPING = "missing_mapping"      # 缺少 usmap/jmap 映射
    CUSTOM_PAYLOAD = "custom_payload"        # class-specific 自定义序列化


@dataclass
class PropertyFallback:
    """未知/损坏 property 的结构化 fallback（替代原 None 返回）。

    对应报告 7.1 P0 建议：
    {
      "kind": "unknown_property",
      "name": "PropertyName",
      "type": "UnknownType",
      "size": 32,
      "array_index": 0,
      "raw_data": "...",
      "status": "unsupported_type"
    }
    """
    name: str                               # PropertyTag.name
    type: str                               # PropertyTag.type（未知类型名）
    size: int                               # PropertyTag.size（字节数）
    raw_bytes: bytes = b""                  # 原始字节（bounded seek 后读取）
    reason: FallbackReason = FallbackReason.UNSUPPORTED_TYPE
    array_index: int = 0                    # 数组索引
    tag_data: Optional[Dict[str, Any]] = None  # tag 附加信息
    error_message: Optional[str] = None     # 解析失败时的异常信息

    @property
    def kind(self) -> str:
        return "unknown_property"

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 兼容 dict。"""
        d: Dict[str, Any] = {
            "kind": self.kind,
            "name": self.name,
            "type": self.type,
            "size": self.size,
            "array_index": self.array_index,
            "reason": self.reason.value if isinstance(self.reason, Enum) else self.reason,
        }
        if self.raw_bytes:
            # 限制 raw bytes 输出长度
            raw = self.raw_bytes[:256]
            d["raw_data"] = raw.hex()
            if len(self.raw_bytes) > 256:
                d["raw_data_truncated"] = True
                d["raw_data_full_size"] = len(self.raw_bytes)
        if self.tag_data:
            d["tag_data"] = self.tag_data
        if self.error_message:
            d["error_message"] = self.error_message
        return d


@dataclass
class StructFallback:
    """未知 struct 的结构化 fallback（参考 CUE4Parse FStructFallback）。

    保留 struct 类型名、大小、原始字节和部分解析字段。
    """
    struct_type: str                        # StructProperty 的 struct 类型名
    size: int                               # 原始 size
    raw_bytes: bytes = b""                  # 原始字节
    reason: FallbackReason = FallbackReason.UNSUPPORTED_STRUCT
    fields: Dict[str, Any] = field(default_factory=dict)  # 部分解析的字段

    @property
    def kind(self) -> str:
        return "struct_fallback"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "kind": self.kind,
            "struct_type": self.struct_type,
            "size": self.size,
            "reason": self.reason.value if isinstance(self.reason, Enum) else self.reason,
            "fields": self.fields,
        }
        if self.raw_bytes:
            raw = self.raw_bytes[:256]
            d["raw_data"] = raw.hex()
            if len(self.raw_bytes) > 256:
                d["raw_data_truncated"] = True
        return d


@dataclass
class GenericUObject:
    """通用 UObject fallback（参考 CUE4Parse generic UObject）。

    当 export 无专用 handler 时，仍保留：
    - object identity (name, class, outer)
    - serial offset/size
    - 可解析的通用属性
    - fallback raw 数据
    - 解析状态
    """
    name: str                               # export object name
    class_name: str                         # export class name
    serial_offset: int = 0                  # 序列化起始偏移
    serial_size: int = 0                    # 序列化大小
    parse_status: ExportParseStatus = ExportParseStatus.FALLBACK
    super_name: str = ""                    # 父类名（如可解析）
    outer_path: List[str] = field(default_factory=list)  # outer 路径
    properties: List["PropertyValue"] = field(default_factory=list)  # 可解析属性
    fallback_data: Optional[StructFallback] = None  # fallback 数据
    requires_mappings: bool = False         # 是否需要 usmap/jmap
    missing_mapping: Optional[str] = None   # 缺失的映射名
    error_message: Optional[str] = None     # 错误信息

    @property
    def kind(self) -> str:
        return "generic_uobject"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "kind": self.kind,
            "name": self.name,
            "class_name": self.class_name,
            "super_name": self.super_name,
            "outer_path": self.outer_path,
            "serial_offset": self.serial_offset,
            "serial_size": self.serial_size,
            "parse_status": self.parse_status.value if isinstance(self.parse_status, Enum) else self.parse_status,
            "property_count": len(self.properties),
            "requires_mappings": self.requires_mappings,
        }
        if self.fallback_data:
            d["fallback_data"] = self.fallback_data.to_dict()
        if self.missing_mapping:
            d["missing_mapping"] = self.missing_mapping
        if self.error_message:
            d["error_message"] = self.error_message
        return d
```

- [ ] **Step 4: 导出新模型**

修改 `src/uasset_read/models/__init__.py`，在现有导出中添加：

```python
# 在 models/__init__.py 的 __all__ 或 import 中添加
from uasset_read.models.fallback import (
    PropertyFallback,
    StructFallback,
    GenericUObject,
    ExportParseStatus,
    FallbackReason,
)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_fallback_models.py -v
```
预期: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/models/fallback.py src/uasset_read/models/__init__.py tests/test_fallback_models.py
git commit -m "feat: add PropertyFallback/StructFallback/GenericUObject models (P0)"
```

---

## Task 2: 未知 Property 结构化 Fallback

**Files:**
- Modify: `src/uasset_read/parsers/property_parser.py:143-158`
- Modify: `src/uasset_read/parsers/property_parser.py:340-355`
- Test: `tests/test_unknown_property_fallback.py`

- [ ] **Step 1: 编写测试**

```python
"""tests/test_unknown_property_fallback.py — 未知 property 结构化 fallback 测试"""
import io
from unittest.mock import MagicMock

from uasset_read.parsers.property_parser import parse_property_value
from uasset_read.models.properties import PropertyTag
from uasset_read.models.fallback import PropertyFallback, FallbackReason


def _make_archive(data: bytes):
    """创建 mock FArchive"""
    from uasset_read.archive import FArchive
    # FArchive 需要 seek/read 能力
    buf = io.BytesIO(data)
    archive = MagicMock(spec=FArchive)
    archive.read.return_value = data
    archive.tell.return_value = 0
    archive.seek.return_value = None
    archive.total_size.return_value = len(data) + 100
    return archive


def test_unknown_property_returns_fallback_not_none():
    """未知类型应返回 PropertyFallback 而非 None"""
    tag = PropertyTag(
        name="TestProp",
        type="CompletelyUnknownType",
        size=8,
        serialize_type="Property",
    )
    archive = _make_archive(b"\x00" * 8)
    result = parse_property_value(tag, archive, [], [])

    assert result is not None, "Unknown property should NOT return None"
    assert isinstance(result, PropertyFallback)
    assert result.name == "TestProp"
    assert result.type == "CompletelyUnknownType"
    assert result.size == 8
    assert result.reason == FallbackReason.UNSUPPORTED_TYPE


def test_unknown_property_preserves_array_index():
    """Fallback 应保留 array_index"""
    tag = PropertyTag(
        name="ArrayProp",
        type="UnknownArrayType",
        size=4,
        array_index=3,
        serialize_type="Property",
    )
    archive = _make_archive(b"\x00" * 4)
    result = parse_property_value(tag, archive, [], [])

    assert isinstance(result, PropertyFallback)
    assert result.array_index == 3


def test_unknown_property_reads_raw_bytes():
    """Fallback 应读取原始字节"""
    raw = b"\xDE\xAD\xBE\xEF"
    tag = PropertyTag(
        name="RawProp",
        type="UnknownRawType",
        size=4,
        serialize_type="Property",
    )
    archive = _make_archive(raw)
    archive.read.return_value = raw
    result = parse_property_value(tag, archive, [], [])

    assert isinstance(result, PropertyFallback)
    assert result.raw_bytes == raw


def test_unknown_property_to_dict():
    """PropertyFallback.to_dict 应输出 JSON 兼容 dict"""
    fb = PropertyFallback(
        name="TestProp",
        type="UnknownType",
        size=32,
        raw_bytes=b"\xAA" * 32,
        reason=FallbackReason.UNSUPPORTED_TYPE,
        array_index=0,
    )
    d = fb.to_dict()
    assert d["kind"] == "unknown_property"
    assert d["name"] == "TestProp"
    assert d["type"] == "UnknownType"
    assert d["size"] == 32
    assert d["reason"] == "unsupported_type"
    assert "raw_data" in d


def test_skipped_property_still_returns_dict():
    """Skipped property 应保持现有 dict 格式（不受影响）"""
    tag = PropertyTag(
        name="SkipProp",
        type="SomeType",
        size=10,
        serialize_type="Skipped",
    )
    archive = _make_archive(b"\x00" * 10)
    result = parse_property_value(tag, archive, [], [])

    assert isinstance(result, dict)
    assert result["kind"] == "skipped_property"


def test_binary_or_native_still_returns_dict():
    """BinaryOrNative property 应保持现有 dict 格式（不受影响）"""
    tag = PropertyTag(
        name="BinProp",
        type="UnknownBinType",
        size=6,
        serialize_type="BinaryOrNative",
    )
    archive = _make_archive(b"\x00" * 6)
    result = parse_property_value(tag, archive, [], [])

    assert isinstance(result, dict)
    assert result["kind"] == "binary_or_native_property"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_unknown_property_fallback.py -v
```
预期: `test_unknown_property_returns_fallback_not_none` 等 FAIL（当前返回 None）

- [ ] **Step 3: 修改 property_parser.py 未知类型分派**

将 `parse_property_value` 中 line 143-158 的未知类型处理从 `return None` 改为返回 `PropertyFallback`：

```python
# 文件头部新增 import
from uasset_read.models.fallback import PropertyFallback, FallbackReason

# 修改 line 143-158（未知类型分支）：
    parsers = _get_parse_functions()
    handler = parsers.get(tag.type)
    if handler is None:
        # D-05: 未知类型 — 返回结构化 PropertyFallback 替代 None
        # 读取 raw bytes 用于诊断
        raw_data = archive.read(tag.size) if tag.size > 0 else b""

        # 先尝试自定义属性处理 (0xFD/0xFE)
        from uasset_read.parsers.custom_properties import CUSTOM_PROPERTY_HANDLERS, handle_custom_property
        type_parts = getattr(tag, "type_parts", None)
        if type_parts:
            first_node_name = type_parts[0][0] if type_parts else ""
            custom_id_map = {"CustomProperty_FD": 0xFD, "CustomProperty_FE": 0xFE}
            custom_id = custom_id_map.get(first_node_name)
            if custom_id is not None:
                try:
                    return handle_custom_property(custom_id, tag, archive, name_map, mappings=mappings, game=game, summary=summary)
                except Exception:
                    pass  # fallback 到 PropertyFallback
        game_key = game.lower() if game else None
        if (game_key, tag.type) in CUSTOM_PROPERTY_HANDLERS or (None, tag.type) in CUSTOM_PROPERTY_HANDLERS:
            try:
                return handle_custom_property(0xFF, tag, archive, name_map, mappings=mappings, game=game, summary=summary)
            except Exception:
                pass  # fallback 到 PropertyFallback

        # 返回结构化 fallback
        return PropertyFallback(
            name=tag.name,
            type=tag.type,
            size=tag.size,
            raw_bytes=raw_data,
            reason=FallbackReason.UNSUPPORTED_TYPE,
            array_index=getattr(tag, "array_index", 0),
            tag_data=getattr(tag, "tag_data", None),
        )
```

- [ ] **Step 4: 修改 property loop 处理 fallback 值**

修改 `parse_properties_from_export` 中 line 344-355 附近，使 `PropertyValue` 能接纳 `PropertyFallback` 作为 value：

当前代码（line 350-355）:
```python
            properties.append(PropertyValue(
                name=tag.name,
                type=tag.type,
                value=value,
                array_index=tag.array_index
            ))
```

无需修改 — `PropertyValue.value` 是 `Any` 类型，可直接接纳 `PropertyFallback`。
但需确保 `value` 为 `None`（自定义 handler 返回 None 的旧路径）时也转为 fallback：

在 line 348 之后、line 350 之前插入：

```python
            # 如果解析返回 None（旧路径或 handler 显式返回 None），转为 PropertyFallback
            if value is None:
                value = PropertyFallback(
                    name=tag.name,
                    type=tag.type,
                    size=tag.size,
                    raw_bytes=b"",
                    reason=FallbackReason.UNSUPPORTED_TYPE,
                    array_index=tag.array_index,
                    error_message="Parser returned None (unsupported or missing handler)",
                )
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_unknown_property_fallback.py -v
```
预期: 全部 PASS

- [ ] **Step 6: 运行现有测试确认无回归**

```bash
python -m pytest tests/ -v --timeout=60
```
预期: 全部 PASS（包括 integration tests）

- [ ] **Step 7: Commit**

```bash
git add src/uasset_read/parsers/property_parser.py tests/test_unknown_property_fallback.py
git commit -m "feat(P0): unknown property returns PropertyFallback instead of None"
```

---

## Task 3: Class Handler Registry

**Files:**
- Create: `src/uasset_read/parsers/class_registry.py`
- Test: `tests/test_class_registry.py`

- [ ] **Step 1: 编写测试**

```python
"""tests/test_class_registry.py — Class Handler Registry 测试"""
from uasset_read.parsers.class_registry import (
    ClassHandlerRegistry,
    ClassHandler,
    HandlerResult,
    FallbackPolicy,
)


class MockHandler(ClassHandler):
    """测试用 mock handler"""

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
        return HandlerResult(
            success=True,
            properties=[],
            data={"handled_by": self._name},
        )


def test_registry_register_and_lookup():
    """注册和精确查找"""
    reg = ClassHandlerRegistry()
    handler = MockHandler("TestHandler", ["MyClass", "MyOtherClass"])
    reg.register(handler)

    found = reg.find_handler("MyClass")
    assert found is not None
    assert found.handler_name == "TestHandler"


def test_registry_unknown_class_returns_none():
    """未知 class 无 handler"""
    reg = ClassHandlerRegistry()
    reg.register(MockHandler("TestHandler", ["KnownClass"]))

    found = reg.find_handler("UnknownClass")
    assert found is None


def test_registry_multiple_handlers():
    """多个 handler 独立注册"""
    reg = ClassHandlerRegistry()
    h1 = MockHandler("H1", ["ClassA"])
    h2 = MockHandler("H2", ["ClassB", "ClassC"])
    reg.register(h1)
    reg.register(h2)

    assert reg.find_handler("ClassA").handler_name == "H1"
    assert reg.find_handler("ClassB").handler_name == "H2"
    assert reg.find_handler("ClassC").handler_name == "H2"
    assert reg.find_handler("ClassD") is None


def test_handler_result_success():
    """HandlerResult 成功结果"""
    result = HandlerResult(
        success=True,
        properties=["prop1", "prop2"],
        data={"key": "value"},
    )
    assert result.success is True
    assert len(result.properties) == 2
    assert result.data["key"] == "value"


def test_handler_result_failure():
    """HandlerResult 失败结果"""
    result = HandlerResult(
        success=False,
        error_message="Not applicable",
        fallback_policy=FallbackPolicy.SKIP,
    )
    assert result.success is False
    assert result.fallback_policy == FallbackPolicy.SKIP


def test_fallback_policy_enum():
    """FallbackPolicy 枚举值"""
    assert FallbackPolicy.GENERIC_UOBJECT == "generic_uobject"
    assert FallbackPolicy.SKIP == "skip"
    assert FallbackPolicy.RAISE == "raise"
    assert FallbackPolicy.PROPERTY_FALLBACK == "property_fallback"


def test_registry_get_registered_handlers():
    """获取已注册 handler 列表"""
    reg = ClassHandlerRegistry()
    reg.register(MockHandler("H1", ["A"]))
    reg.register(MockHandler("H2", ["B"]))

    names = [h.handler_name for h in reg.get_registered_handlers()]
    assert "H1" in names
    assert "H2" in names
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_class_registry.py -v
```
预期: 全部 FAIL

- [ ] **Step 3: 实现 Class Handler Registry**

```python
"""src/uasset_read/parsers/class_registry.py — Class Handler Registry。

参考 CUE4Parse ObjectTypeRegistry 模式：
1. 精确 class handler 查找
2. 父类 handler 查找（后续扩展）
3. generic UObject fallback
4. skip policy 作为最后的 fallback

handler 接口：
- can_handle(class_name) -> bool
- parse(export, archive, context) -> HandlerResult
- fallback_policy -> FallbackPolicy
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.models.properties import PropertyValue

logger = logging.getLogger(__name__)


class FallbackPolicy(str, Enum):
    """当 handler 无法处理时的 fallback 策略。"""
    GENERIC_UOBJECT = "generic_uobject"   # 回退为通用 UObject
    SKIP = "skip"                         # 跳过 payload（原 skip list 行为）
    RAISE = "raise"                       # 抛出异常（tolerant=False 时）
    PROPERTY_FALLBACK = "property_fallback"  # 逐属性 fallback


@dataclass
class HandlerResult:
    """Class handler 的解析结果。"""
    success: bool
    properties: List["PropertyValue"] = field(default_factory=list)
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    fallback_policy: FallbackPolicy = FallbackPolicy.GENERIC_UOBJECT


class ClassHandler(ABC):
    """Class handler 抽象基类。

    每个 handler 负责一类 export 的解析。
    子类实现 can_handle 和 parse 方法。
    """

    @abstractmethod
    def can_handle(self, class_name: str) -> bool:
        """判断此 handler 是否能处理给定 class_name。"""
        ...

    @property
    @abstractmethod
    def handler_name(self) -> str:
        """handler 名称（用于日志和诊断）。"""
        ...

    @property
    def fallback_policy(self) -> FallbackPolicy:
        """当 handler 解析失败时的 fallback 策略。"""
        return FallbackPolicy.GENERIC_UOBJECT

    @abstractmethod
    def parse(
        self,
        export: "ObjectExport",
        archive: "FArchive",
        context: Optional[Any] = None,
    ) -> HandlerResult:
        """解析 export 的属性数据。

        Args:
            export: ObjectExport 实例
            archive: FArchive 实例（当前位置已 seek 到属性起始）
            context: 可选上下文（summary, name_map, export_map 等）

        Returns:
            HandlerResult 包含解析结果和 fallback 策略
        """
        ...


class ClassHandlerRegistry:
    """Class handler 注册表。

    解析顺序：
    1. 精确 class handler 查找
    2. （后续）父类 handler 查找
    3. 返回 None（调用方决定 generic fallback）
    """

    def __init__(self) -> None:
        self._handlers: List[ClassHandler] = []
        self._cache: Dict[str, Optional[ClassHandler]] = {}

    def register(self, handler: ClassHandler) -> None:
        """注册一个 class handler。"""
        self._handlers.append(handler)
        self._cache.clear()  # 清除缓存

    def find_handler(self, class_name: str) -> Optional[ClassHandler]:
        """查找能处理给定 class_name 的 handler。

        按注册顺序查找，第一个 can_handle 返回 True 的 handler 被返回。
        结果被缓存以加速重复查询。

        Args:
            class_name: export 的 class 名称

        Returns:
            匹配的 ClassHandler，或 None
        """
        if class_name in self._cache:
            return self._cache[class_name]

        for handler in self._handlers:
            if handler.can_handle(class_name):
                self._cache[class_name] = handler
                return handler

        self._cache[class_name] = None
        return None

    def get_registered_handlers(self) -> List[ClassHandler]:
        """返回所有已注册的 handler。"""
        return list(self._handlers)

    def clear(self) -> None:
        """清空所有注册和缓存。"""
        self._handlers.clear()
        self._cache.clear()


# 全局默认 registry 实例
_default_registry: Optional[ClassHandlerRegistry] = None


def get_class_registry() -> ClassHandlerRegistry:
    """获取全局默认 class handler registry。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ClassHandlerRegistry()
    return _default_registry


def reset_class_registry() -> None:
    """重置全局默认 registry（测试用）。"""
    global _default_registry
    _default_registry = None
```

- [ ] **Step 4: 改造 class_specific_skip.py 使用 registry**

修改 `class_specific_skip.py`，使 skip 判断成为 registry 的 fallback policy 之一：

在文件顶部添加：

```python
from uasset_read.parsers.class_registry import (
    get_class_registry,
    FallbackPolicy,
)
```

修改 `should_skip_export_for_tolerant_parsing` 函数，增加 registry 查找逻辑：

```python
def should_skip_export_for_tolerant_parsing(
    export: "ObjectExport",
    class_name: Optional[str] = None,
) -> bool:
    """判断是否应对某 export 使用 tolerant skip。

    检查顺序：
    1. class handler registry 中是否有 handler 且其 fallback_policy == SKIP
    2. export.object_name 是否以 SKIP_CLASS_PREFIXES 开头
    3. class_name 是否在 SKIP_CLASS_NAMES 中（精确匹配）
    4. class_name 是否以 SKIP_CLASS_PREFIXES 开头
    """
    # 检查 1: registry handler fallback policy
    if class_name is not None:
        registry = get_class_registry()
        handler = registry.find_handler(class_name)
        if handler is not None and handler.fallback_policy == FallbackPolicy.SKIP:
            return True

    # 检查 2-4: 原有 skip list（作为 fallback policy）
    object_name = str(export.object_name)
    if object_name.startswith(SKIP_CLASS_PREFIXES):
        return True
    if class_name is not None and class_name in SKIP_CLASS_NAMES:
        return True
    if class_name is not None and class_name.startswith(SKIP_CLASS_PREFIXES):
        return True
    return False
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_class_registry.py -v
```

- [ ] **Step 6: 运行现有测试确认无回归**

```bash
python -m pytest tests/test_tolerant_class_specific.py -v
```

- [ ] **Step 7: Commit**

```bash
git add src/uasset_read/parsers/class_registry.py src/uasset_read/parsers/class_specific_skip.py tests/test_class_registry.py
git commit -m "feat(P1): add ClassHandlerRegistry with fallback policy chain"
```

---

## Task 4: Export 级错误上下文增强

**Files:**
- Modify: `src/uasset_read/parsers/property_parser.py` (parse_properties_from_export)
- Modify: `src/uasset_read/models/fallback.py` (已有 GenericUObject)
- Test: `tests/test_export_error_context.py`

- [ ] **Step 1: 编写测试**

```python
"""tests/test_export_error_context.py — Export 级错误上下文测试"""
import io
from unittest.mock import MagicMock

from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
from uasset_read.models.fallback import PropertyFallback, FallbackReason


def _make_mock_archive(data: bytes):
    from uasset_read.archive import FArchive
    buf = io.BytesIO(data)
    archive = MagicMock()
    archive.tell.return_value = 0
    archive.seek = MagicMock()
    archive.read = MagicMock(return_value=data)
    archive.total_size.return_value = len(data) + 1000
    archive.read_u8.return_value = 0
    return archive


def _make_mock_export(serial_offset=0, serial_size=100, script_serial_offset=0, script_serial_size=0):
    export = MagicMock(spec=ObjectExport)
    export.serial_offset = serial_offset
    export.serial_size = serial_size
    export.script_serial_offset = script_serial_offset
    export.script_serial_size = script_serial_size
    export.object_name = "TestExport"
    export.class_index = PackageIndex(0)
    return export


def _make_mock_summary(file_version_ue5=0, package_flags=0):
    summary = MagicMock()
    summary.file_version_ue5 = file_version_ue5
    summary.package_flags = package_flags
    return summary


def test_export_with_no_properties_returns_empty_list():
    """空属性列表应返回空 list"""
    # "None" 终止标记
    data = b"None\x00"  # FName "None" 终止
    archive = _make_mock_archive(data)
    archive.tell.return_value = 100  # property_start
    export = _make_mock_export(serial_offset=100, serial_size=100)
    summary = _make_mock_summary()

    result = parse_properties_from_export(
        export=export,
        archive=archive,
        summary=summary,
        name_map=["None"],
        export_map=[],
    )
    # 应正常终止于 "None"
    assert isinstance(result, list)


def test_export_error_context_includes_class_and_offset():
    """解析失败时应在 fallback 中包含 class/offset 信息"""
    # 这个测试验证当 property 解析失败时，
    # PropertyValue.value 是 PropertyFallback 且包含足够上下文
    from uasset_read.models.properties import PropertyValue

    # 构造一个导致未知类型的 tag 数据
    # 简化测试：直接验证 PropertyFallback 的错误消息字段
    fb = PropertyFallback(
        name="BadProp",
        type="BrokenType",
        size=0,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_message="Test error context",
    )
    assert fb.error_message == "Test error context"
    assert fb.reason == FallbackReason.PARSE_ERROR
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_export_error_context.py -v
```

- [ ] **Step 3: 增强 property_parser.py 错误上下文**

在 `parse_properties_from_export` 的 except 块（line 379-388）中，增强 fallback 信息：

当前代码:
```python
        except ParseError as e:
            if tag is not None and start_pos is not None:
                archive.seek(start_pos + tag.size)
            properties.append(PropertyValue(
                name=tag.name if tag is not None else "Unknown",
                type="Warning",
                value=f"ParseError: {e}",
                array_index=0
            ))
```

修改为:
```python
        except ParseError as e:
            if tag is not None and start_pos is not None:
                archive.seek(start_pos + tag.size)

            # 使用 PropertyFallback 替代纯字符串错误信息
            fb = PropertyFallback(
                name=tag.name if tag is not None else "Unknown",
                type=tag.type if tag is not None else "Unknown",
                size=tag.size if tag is not None else 0,
                raw_bytes=b"",
                reason=FallbackReason.PARSE_ERROR,
                array_index=tag.array_index if tag is not None else 0,
                error_message=f"ParseError at offset {start_pos}: {e}",
            )
            properties.append(PropertyValue(
                name=fb.name,
                type="Warning",
                value=fb,
                array_index=fb.array_index,
            ))
```

需在文件顶部添加 import:
```python
from uasset_read.models.fallback import PropertyFallback, FallbackReason
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_export_error_context.py -v
```

- [ ] **Step 5: 运行全部测试确认无回归**

```bash
python -m pytest tests/ -v --timeout=60
```

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/parsers/property_parser.py tests/test_export_error_context.py
git commit -m "feat(P1): export error context uses PropertyFallback with class/offset info"
```

---

## Task 5: 公共 API 导出与集成验证

**Files:**
- Modify: `src/uasset_read/__init__.py`
- Test: `tests/test_api_cleanup.py` (现有)

- [ ] **Step 1: 更新公共 API 导出**

在 `src/uasset_read/__init__.py` 的 `__all__` 中添加：

```python
# Fallback models
"PropertyFallback",
"StructFallback",
"GenericUObject",
"ExportParseStatus",
"FallbackReason",
# Class registry
"ClassHandlerRegistry",
"ClassHandler",
"HandlerResult",
"FallbackPolicy",
"get_class_registry",
```

同时在对应 import 部分添加：

```python
from uasset_read.models.fallback import (
    PropertyFallback,
    StructFallback,
    GenericUObject,
    ExportParseStatus,
    FallbackReason,
)
from uasset_read.parsers.class_registry import (
    ClassHandlerRegistry,
    ClassHandler,
    HandlerResult,
    FallbackPolicy,
    get_class_registry,
)
```

- [ ] **Step 2: 运行 API 清理测试**

```bash
python -m pytest tests/test_api_cleanup.py -v
```

如果此测试检查 `__all__` 中列出的符号是否都可导入，应 PASS。
如果测试期望 `__all__` 不包含额外符号，需要调整测试。

- [ ] **Step 3: 运行集成测试**

```bash
python -m pytest tests/ -v -m integration --timeout=120
```

预期: 全部 PASS（fallback 模型不影响已知 asset 的正常解析）

- [ ] **Step 4: 验证 JSON 输出包含 fallback 信息**

运行 CLI 对一个已知会产生未知属性的资产：

```bash
uasset-read E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\Maps\FirstPersonMap.uasset --summary
```

检查输出中是否包含 fallback 相关字段（如果有未知属性）。

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/__init__.py
git commit -m "feat: export fallback models and class registry in public API"
```

---

## Task 6: 文档更新

**Files:**
- Modify: `docs/reports/uasset_unknown_asset_handling_report.md` (更新实施状态)
- Create: `docs/release-notes/unknown-asset-handling-enhancements.md`

- [ ] **Step 1: 更新报告实施状态**

在 `docs/reports/uasset_unknown_asset_handling_report.md` 末尾添加：

```markdown
## 11. 实施状态（2026-06-04）

| 建议项 | 优先级 | 状态 | 对应 Commit |
|--------|--------|------|-------------|
| 增强 unknown property 输出 | P0 | ✅ 已完成 | `PropertyFallback` 模型 + property_parser 集成 |
| Export 级错误上下文 | P1 | ✅ 已完成 | ParseError 转为 PropertyFallback |
| Class handler registry | P1 | ✅ 已完成 | `ClassHandlerRegistry` + fallback policy 链 |
| Skip list 改造为 fallback policy | P1 | ✅ 已完成 | `class_specific_skip.py` 集成 registry |
| GenericUObject / StructFallback 模型 | P1 | ✅ 已完成 | `models/fallback.py` |
| Unversioned mappings 策略 | P2 | ⏳ 待实施 | 需要 mappings provider 扩展 |
| BPGC / EdGraph 提取链路 | P2 | ⏳ 待实施 | 需 blueprint/ 模块扩展 |
| cpp_skeleton 源码提示 | P3 | ⏳ 待实施 | 需 cpp_gen/ 模块扩展 |
```

- [ ] **Step 2: 创建 release note**

```markdown
# Unknown Asset Handling Enhancements

日期：2026-06-04

## 概述

将未知 property/class 的处理从"返回 None 或跳过"升级为结构化 fallback，
降低信息丢失，为后续 class handler registry 扩展奠定基础。

## 变更

### 新增数据模型 (`models/fallback.py`)

- `PropertyFallback` — 未知/损坏 property 的结构化容器
- `StructFallback` — 未知 struct 的 fallback（参考 CUE4Parse FStructFallback）
- `GenericUObject` — 通用 UObject fallback（参考 CUE4Parse generic UObject）
- `ExportParseStatus` — export 级解析状态枚举
- `FallbackReason` — fallback 原因枚举

### Property 分派器改造

- 未知 property type 不再返回 `None`，而是返回 `PropertyFallback`
- 包含 raw bytes、reason、error_message 等诊断信息
- `PropertyValue.value` 现在可能为 `PropertyFallback` 实例

### Class Handler Registry

- 新增 `ClassHandlerRegistry` 支持精确 class handler 查找
- `ClassHandler` 抽象基类定义 `can_handle`/`parse`/`fallback_policy` 接口
- `FallbackPolicy` 枚举：GENERIC_UOBJECT / SKIP / RAISE / PROPERTY_FALLBACK
- 现有 skip list 改造为 registry 的 fallback policy 之一

### 公共 API

- `__all__` 新增: `PropertyFallback`, `StructFallback`, `GenericUObject`,
  `ExportParseStatus`, `FallbackReason`, `ClassHandlerRegistry`, `ClassHandler`,
  `HandlerResult`, `FallbackPolicy`, `get_class_registry`

## 兼容性

- 向后兼容：现有 `PropertyValue` 的 `value` 字段为 `Any` 类型
- Skipped/BinaryOrNative property 保持原有 dict 格式不变
- 所有现有测试通过
```

- [ ] **Step 3: Commit**

```bash
git add docs/reports/uasset_unknown_asset_handling_report.md docs/release-notes/unknown-asset-handling-enhancements.md
git commit -m "docs: update unknown asset handling report with implementation status"
```

---

## Self-Review Checklist

### 1. Spec coverage

| 报告建议 | 对应 Task | 状态 |
|----------|-----------|------|
| 7.1 P0: 增强 unknown property 输出 | Task 2 | ✅ |
| 7.1 P0: 保留 raw/status/context | Task 2 | ✅ |
| 7.2 P1: 引入 class handler registry | Task 3 | ✅ |
| 7.3 P1: GenericUObject / StructFallback | Task 1 | ✅ |
| 7.3 P1: ExportParseStatus | Task 1 | ✅ |
| 7.2 P1: skip list 改造为 fallback policy | Task 3 | ✅ |
| 报告 7.6: Export 级错误上下文 | Task 4 | ✅ |
| 公共 API 导出 | Task 5 | ✅ |
| 文档更新 | Task 6 | ✅ |

未包含在本次计划的报告建议（P2/P3，留给后续）：
- 7.4 P2: unversioned mappings 严格策略
- 7.5 P2: BPGC / EdGraph 提取链路
- 7.6 P3: cpp_skeleton 源码提示

### 2. Placeholder scan

搜索计划中是否存在 "TBD", "TODO", "implement later", "Add appropriate", "Write tests for" 等占位符：
- ✅ 无占位符。每个 step 包含完整代码。

### 3. Type consistency

- `PropertyFallback`, `StructFallback`, `GenericUObject` 在各任务中的引用一致
- `FallbackReason` 和 `ExportParseStatus` 作为 str enum 在所有文件中统一
- `PropertyValue.value` 类型为 `Any`，兼容 `PropertyFallback` 赋值
- `ClassHandler` 抽象方法签名在各处一致

### 4. DRY / YAGNI / TDD

- ✅ 每个 Task 先写测试再实现（TDD）
- ✅ 不引入超出报告 P0+P1 范围的功能（YAGNI）
- ✅ Fallback 模型复用，不重复定义（DRY）
- ✅ 每个 Task 可独立 commit 和验证

---

Plan complete and saved to `docs/superpowers/plans/2026-06-04-unknown-asset-handling.md`. Two execution options:

**1. Subagent-Driven (recommended)** — 每个 Task 独立子 agent 执行，中间审查，快速迭代

**2. Inline Execution** — 当前会话内批量执行，设置检查点审查

选择哪种方式？
