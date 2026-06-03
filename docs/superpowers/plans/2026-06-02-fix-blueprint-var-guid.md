# Blueprint Variable VarGuid 解析修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Blueprint 变量的 `var_guid` 字段始终为空的问题，使集成测试 `test_real_blueprint_graph_metadata_has_standard_references` 和 `test_real_anim_blueprint_graph_metadata_has_standard_references` 通过。

**Architecture:** 在 `_guid_from_description` 函数中增加对 `StructValue(struct_type="Guid")` 格式的支持，将其 `{A, B, C, D}` 四个 uint32 字段转换为标准 GUID 字符串。同时在 `STRUCT_PROPERTY_DEFAULTS` 中确认 `FBPVariableDescription` 的 `VarGuid` 字段类型映射正确。

**Tech Stack:** Python 3.10+, uasset_read 解析器

---

## 问题根因

`_guid_from_description`（`variable_extractor.py:370`）不识别 `StructValue` 类型的 Guid 值：

| 输入类型 | 当前结果 | 预期 |
|---------|---------|------|
| `StructValue(Guid, {A:int, B:int, C:int, D:int})` | `""` ❌ | 十六进制 GUID 字符串 |
| `dict(kind="binary_or_native_property", raw_data=bytes16)` | ✅ | |
| `bytes` (16字节) | ✅ | |
| `str` | ✅ | |

`FBPVariableDescription` 序列化中的 `VarGuid` 字段被 `StructProperty` 解析器解析为 `StructValue`，而非 `binary_or_native_property` 字典或原始字节。

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/uasset_read/blueprint/variable_extractor.py:370-379` | 修改 | `_guid_from_description` 增加 StructValue 支持 |
| `tests/test_variable_extractor.py` | 修改 | 添加 VarGuid 解析单元测试 |
| `tests/test_sample_assets_representative.py:240-285` | 只读参考 | 集成测试（无需修改） |

---

### Task 1: 修复 `_guid_from_description` 支持 StructValue

**Files:**
- Modify: `src/uasset_read/blueprint/variable_extractor.py:370-379`
- Test: `tests/test_variable_extractor.py`（新增或追加）

- [ ] **Step 1: 编写测试用例**

在 `tests/test_variable_extractor.py` 中添加（如文件不存在则创建）：

```python
"""Blueprint 变量提取器测试。"""
import pytest
from uasset_read.parsers.property_types import StructValue
from uasset_read.blueprint.variable_extractor import _guid_from_description


class TestGuidFromDescription:
    """_guid_from_description 各种输入格式处理。"""

    def test_struct_value_guid(self):
        """StructValue(Guid, {A,B,C,D}) 应转换为十六进制字符串。"""
        sv = StructValue(
            struct_type="Guid",
            fields={"A": 0x01020304, "B": 0x05060708, "C": 0x090A0B0C, "D": 0x0D0E0F10}
        )
        result = _guid_from_description(sv)
        # 4个uint32按小端序字节排列
        assert result != "", "StructValue Guid 不应返回空字符串"
        assert "-" in result, "GUID 应包含连字符分隔符"

    def test_struct_value_zero_guid(self):
        """全零 Guid 也应返回有效字符串。"""
        sv = StructValue(struct_type="Guid", fields={"A": 0, "B": 0, "C": 0, "D": 0})
        result = _guid_from_description(sv)
        assert result != "", "全零 Guid 不应返回空字符串"

    def test_dict_binary_or_native_still_works(self):
        """原有 dict + binary_or_native_property 路径应保持兼容。"""
        d = {
            "kind": "binary_or_native_property",
            "raw_data": b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
        }
        result = _guid_from_description(d)
        assert result == "00010203-0405-0607-0809-0a0b0c0d0e0f"

    def test_bytes_input_still_works(self):
        """原始 bytes 输入应保持兼容。"""
        result = _guid_from_description(b'\xAA\xBB\xCC\xDD' * 4)
        assert result == "aabbccdd-aabb-ccdd-aabb-ccddaabbccdd"

    def test_string_input_passthrough(self):
        """字符串输入应直接返回。"""
        s = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert _guid_from_description(s) == s

    def test_none_returns_empty(self):
        """None 应返回空字符串。"""
        assert _guid_from_description(None) == ""

    def test_int_returns_empty(self):
        """非预期类型应返回空字符串。"""
        assert _guid_from_description(0) == ""
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_variable_extractor.py -v -k TestGuidFromDescription
```

预期：`test_struct_value_guid` 和 `test_struct_value_zero_guid` 失败（`_guid_from_description` 返回 `""`）

- [ ] **Step 3: 实现修复**

在 `src/uasset_read/blueprint/variable_extractor.py` 的 `_guid_from_description` 函数（约第 370 行）中，**在现有检查之前**添加 `StructValue` 处理：

当前代码（约第 370-378 行）：
```python
def _guid_from_description(value: Any) -> str:
    if isinstance(value, dict) and value.get("kind") == "binary_or_native_property":
        raw = value.get("raw_data")
        if isinstance(raw, bytes) and len(raw) == 16:
            return _format_guid_bytes(raw)
    if isinstance(value, bytes) and len(value) == 16:
        return _format_guid_bytes(value)
    if isinstance(value, str):
        return value
    return ""
```

修改为：
```python
def _guid_from_description(value: Any) -> str:
    # StructValue(Guid, {A:int, B:int, C:int, D:int}) — StructProperty 解析结果
    if isinstance(value, StructValue) and value.struct_type == "Guid":
        fields = value.fields
        a = int(fields.get("A", 0))
        b = int(fields.get("B", 0))
        c = int(fields.get("C", 0))
        d = int(fields.get("D", 0))
        # 每个 uint32 按小端序转为 4 字节
        def _u32_to_bytes(v: int) -> bytes:
            return v.to_bytes(4, byteorder='little')
        raw = _u32_to_bytes(a) + _u32_to_bytes(b) + _u32_to_bytes(c) + _u32_to_bytes(d)
        return _format_guid_bytes(raw)

    if isinstance(value, dict) and value.get("kind") == "binary_or_native_property":
        raw = value.get("raw_data")
        if isinstance(raw, bytes) and len(raw) == 16:
            return _format_guid_bytes(raw)
    if isinstance(value, bytes) and len(value) == 16:
        return _format_guid_bytes(value)
    if isinstance(value, str):
        return value
    return ""
```

确保文件顶部导入了 `StructValue`：
```python
from uasset_read.parsers.property_types import StructValue
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_variable_extractor.py -v -k TestGuidFromDescription
```

预期：全部 7 个测试通过

- [ ] **Step 5: 运行集成测试验证**

```bash
UE_SAMPLE_ROOT=E:/Develop/lib/UnrealEngine/Samples python -m pytest tests/test_sample_assets_representative.py::test_real_blueprint_graph_metadata_has_standard_references tests/test_sample_assets_representative.py::test_real_anim_blueprint_graph_metadata_has_standard_references -v
```

预期：两个测试通过（之前因 var_guid 全空而失败）

- [ ] **Step 6: 运行完整测试套件**

```bash
python -m pytest tests/ -v --tb=short -q
```

预期：无新增失败（已有的 2 xfailed 保持不变）

- [ ] **Step 7: 提交**

```bash
git add src/uasset_read/blueprint/variable_extractor.py tests/test_variable_extractor.py
git commit -m "fix: _guid_from_description 支持 StructValue(Guid) 格式，修复 blueprint var_guid 为空"
```

---

## 自审

### 1. 覆盖检查
- [x] StructValue Guid 支持 → Task 1 Step 3
- [x] 单元测试覆盖 → Task 1 Step 1
- [x] 集成测试验证 → Task 1 Step 5
- [x] 回归测试 → Task 1 Step 6

### 2. 占位符扫描
无 "TODO"、"TBD"、"similar to" 等占位符。

### 3. 类型一致性
- `StructValue` 从 `uasset_read.parsers.property_types` 导入，已在代码库中使用
- `_format_guid_bytes` 是同一文件中的现有函数
- 字节序使用 `little`（UE FGuid 序列化标准）
