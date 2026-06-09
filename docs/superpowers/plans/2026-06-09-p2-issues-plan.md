# P2 Issues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two P2 issues — (1) preserve deprecated arrays in PackageFileSummary and (2) expand blueprint_ue_text golden fixtures with repr-free output.

**Architecture:** Issue #46 adds `compressed_chunks` and `additional_packages_to_cook` fields to the PackageFileSummary dataclass, stores the read values, fixes a dormant read-size bug (12 → 16 bytes per FCompressedChunk), and ensures deprecated/owner fields are visible in JSON output. Issue #27 adds golden fixtures for 4 missing node types (EnhancedInputAction, Interface Call, Macro, Delegate), hardens the repr-free fallback in `_format_ue_value`, and adds a `blueprint_text` vs `blueprint_ue_text` differentiation docstring.

**Tech Stack:** Python 3.10+, pytest, dataclasses

---

## Part A: Issue #46 — PackageFileSummary 字段保留

### Task 1: Add deprecated array fields to PackageFileSummary dataclass

**Files:**
- Modify: `src/uasset_read/serializers/package_summary.py:62-116`

- [ ] **Step 1: Add `compressed_chunks` and `additional_packages_to_cook` fields**

Add after the existing `owner_persistent_guid` field (line ~99):

```python
    owner_persistent_guid: str = ""  # 16 bytes GUID (UE4 519 or legacy -7/-8)
    compressed_chunks: List[dict] = field(default_factory=list)  # 已废弃，保留用于偏移对齐
    additional_packages_to_cook: List[str] = field(default_factory=list)  # 已废弃
```

Each compressed chunk is a dict with keys: `uncompressed_offset`, `uncompressed_size`, `compressed_offset`, `compressed_size`.

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `python -m pytest tests/test_package_summary_owner_guid.py tests/test_package_summary_fields.py -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add src/uasset_read/serializers/package_summary.py
git commit -m "feat: add deprecated array fields to PackageFileSummary dataclass"
```

---

### Task 2: Store deprecated arrays during reading

**Files:**
- Modify: `src/uasset_read/serializers/package_summary.py:340-355` (UE4 path)
- Modify: `src/uasset_read/serializers/package_summary.py:705-720` (UE5 path)

- [ ] **Step 1: Fix FCompressedChunk read size (12 → 16 bytes) and store values in UE4 path**

Replace lines 340-345:

```python
    # CompressedChunks (已废弃，保留用于偏移对齐)
    compressed_chunks_count = archive.read_i32()
    if compressed_chunks_count < 0:
        raise ParseError(f"Negative compressed chunks count: {compressed_chunks_count}")
    compressed_chunks = []
    for _ in range(compressed_chunks_count):
        chunk_data = archive.read(16)  # FCompressedChunk: 4 × int32 = 16 bytes
        uncompressed_offset = int.from_bytes(chunk_data[0:4], 'little', signed=True)
        uncompressed_size = int.from_bytes(chunk_data[4:8], 'little', signed=True)
        compressed_offset = int.from_bytes(chunk_data[8:12], 'little', signed=True)
        compressed_size = int.from_bytes(chunk_data[12:16], 'little', signed=True)
        compressed_chunks.append({
            "uncompressed_offset": uncompressed_offset,
            "uncompressed_size": uncompressed_size,
            "compressed_offset": compressed_offset,
            "compressed_size": compressed_size,
        })
```

- [ ] **Step 2: Store AdditionalPackagesToCook in UE4 path**

Replace lines 350-355:

```python
    # AdditionalPackagesToCook (已废弃)
    additional_packages_count = archive.read_i32()
    if additional_packages_count < 0:
        raise ParseError(f"Negative additional packages count: {additional_packages_count}")
    additional_packages_to_cook = []
    for _ in range(additional_packages_count):
        additional_packages_to_cook.append(archive.read_fstring())
```

- [ ] **Step 3: Apply same fixes to UE5 path**

Replace lines 705-710 (UE5 CompressedChunks):

```python
    # 第 21 步：CompressedChunks（已废弃，保留用于偏移对齐）
    compressed_chunks_count = archive.read_i32()
    if compressed_chunks_count < 0:
        raise ParseError(f"Negative compressed chunks count: {compressed_chunks_count}")
    compressed_chunks = []
    for _ in range(compressed_chunks_count):
        chunk_data = archive.read(16)  # FCompressedChunk: 4 × int32 = 16 bytes
        uncompressed_offset = int.from_bytes(chunk_data[0:4], 'little', signed=True)
        uncompressed_size = int.from_bytes(chunk_data[4:8], 'little', signed=True)
        compressed_offset = int.from_bytes(chunk_data[8:12], 'little', signed=True)
        compressed_size = int.from_bytes(chunk_data[12:16], 'little', signed=True)
        compressed_chunks.append({
            "uncompressed_offset": uncompressed_offset,
            "uncompressed_size": uncompressed_size,
            "compressed_offset": compressed_offset,
            "compressed_size": compressed_size,
        })
```

Replace lines 716-720 (UE5 AdditionalPackagesToCook):

```python
    # 第 23 步：AdditionalPackagesToCook（已废弃）
    additional_packages_count = archive.read_i32()
    if additional_packages_count < 0:
        raise ParseError(f"Negative additional packages count: {additional_packages_count}")
    additional_packages_to_cook = []
    for _ in range(additional_packages_count):
        additional_packages_to_cook.append(archive.read_fstring())
```

- [ ] **Step 4: Pass new fields to PackageFileSummary constructor**

Find both return statements (UE4 path returns around line 395, UE5 path returns around line 765) and add the new fields:

```python
    return PackageFileSummary(
        # ... existing fields ...
        owner_persistent_guid=owner_persistent_guid,
        compressed_chunks=compressed_chunks,
        additional_packages_to_cook=additional_packages_to_cook,
        # ... remaining fields ...
    )
```

- [ ] **Step 5: Run tests to verify no regression**

Run: `python -m pytest tests/test_package_summary_owner_guid.py tests/test_package_summary_fields.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/serializers/package_summary.py
git commit -m "fix: store deprecated arrays and fix FCompressedChunk read size (12→16)"
```

---

### Task 3: Verify deprecated fields appear in JSON output

**Files:**
- Create: `tests/test_package_summary_deprecated_fields.py`

- [ ] **Step 1: Write test for deprecated field storage**

```python
"""Tests for PackageFileSummary deprecated array fields (#46)."""
import pytest
from uasset_read.serializers.package_summary import PackageFileSummary


def test_compressed_chunks_default_empty():
    """compressed_chunks 默认为空列表。"""
    summary = PackageFileSummary(tag=0, legacy_file_version=-8, file_version_ue4=519)
    assert summary.compressed_chunks == []
    assert isinstance(summary.compressed_chunks, list)


def test_additional_packages_default_empty():
    """additional_packages_to_cook 默认为空列表。"""
    summary = PackageFileSummary(tag=0, legacy_file_version=-8, file_version_ue4=519)
    assert summary.additional_packages_to_cook == []
    assert isinstance(summary.additional_packages_to_cook, list)


def test_compressed_chunks_stores_values():
    """compressed_chunks 可存储 chunk 字典。"""
    chunks = [
        {
            "uncompressed_offset": 0,
            "uncompressed_size": 1024,
            "compressed_offset": 0,
            "compressed_size": 512,
        }
    ]
    summary = PackageFileSummary(
        tag=0, legacy_file_version=-8, file_version_ue4=519,
        compressed_chunks=chunks,
    )
    assert len(summary.compressed_chunks) == 1
    assert summary.compressed_chunks[0]["uncompressed_size"] == 1024
    assert summary.compressed_chunks[0]["compressed_size"] == 512


def test_additional_packages_stores_values():
    """additional_packages_to_cook 可存储包名列表。"""
    packages = ["/Game/Maps/Level1", "/Game/Maps/Level2"]
    summary = PackageFileSummary(
        tag=0, legacy_file_version=-8, file_version_ue4=519,
        additional_packages_to_cook=packages,
    )
    assert summary.additional_packages_to_cook == packages


def test_owner_persistent_guid_still_works():
    """owner_persistent_guid 字段不受新增字段影响。"""
    summary = PackageFileSummary(
        tag=0, legacy_file_version=-8, file_version_ue4=519,
        owner_persistent_guid="a1b2c3d4e5f67890abcdef1234567890",
    )
    assert summary.owner_persistent_guid == "a1b2c3d4e5f67890abcdef1234567890"
    assert summary.compressed_chunks == []
    assert summary.additional_packages_to_cook == []
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/test_package_summary_deprecated_fields.py -v`
Expected: All 5 tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_package_summary_deprecated_fields.py
git commit -m "test: add tests for deprecated array fields in PackageFileSummary"
```

---

### Task 4: Expose deprecated fields in JSON output

**Files:**
- Modify: `src/uasset_read/renderers/json_renderer.py:49-56`
- Modify: `src/uasset_read/models/ir.py:13-21`

- [ ] **Step 1: Add deprecated fields to PackageHeaderIR**

```python
@dataclass
class PackageHeaderIR:
    """包头部精简摘要。"""
    package_name: str
    package_class: str
    package_flags: int
    total_export_count: int
    total_import_count: int
    ue_version: str
    # 已废弃/版本门控字段（可选）
    owner_persistent_guid: str = ""
    compressed_chunks: list = field(default_factory=list)
    additional_packages_to_cook: list = field(default_factory=list)
```

- [ ] **Step 2: Populate new fields in ir_builder.py**

Find the `PackageHeaderIR` construction (around line 234) and add:

```python
        owner_persistent_guid=_safe_str(getattr(summary, "owner_persistent_guid", "")),
        compressed_chunks=list(getattr(summary, "compressed_chunks", None) or []),
        additional_packages_to_cook=list(getattr(summary, "additional_packages_to_cook", None) or []),
```

- [ ] **Step 3: Add deprecated fields to JSON renderer summary dict**

In `json_renderer.py`, add to the summary dict (after line 55):

```python
            "summary": {
                "package_name": ir.header.package_name,
                "package_class": ir.header.package_class,
                "package_flags": ir.header.package_flags,
                "total_export_count": ir.header.total_export_count,
                "total_import_count": ir.header.total_import_count,
                "ue_version": ir.header.ue_version,
                # 已废弃/版本门控字段
                "owner_persistent_guid": ir.header.owner_persistent_guid or None,
                "compressed_chunks": ir.header.compressed_chunks or None,
                "additional_packages_to_cook": ir.header.additional_packages_to_cook or None,
            },
```

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/test_package_summary_deprecated_fields.py tests/test_package_summary_owner_guid.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/models/ir.py src/uasset_read/ir_builder.py src/uasset_read/renderers/json_renderer.py
git commit -m "feat: expose deprecated/owner fields in IR and JSON output"
```

---

### Task 5: Full test suite verification for Part A

- [ ] **Step 1: Run full test suite**

Run: `python scripts/test_matrix.py smoke`
Expected: 100% pass rate

---

## Part B: Issue #27 — blueprint_ue_text Golden Fixtures

### Task 6: Add golden fixtures for missing node types

**Files:**
- Create: `tests/fixtures/ue_editor_blueprint_text/enhanced_input_action.txt`
- Create: `tests/fixtures/ue_editor_blueprint_text/interface_call.txt`
- Create: `tests/fixtures/ue_editor_blueprint_text/macro.txt`
- Create: `tests/fixtures/ue_editor_blueprint_text/delegate.txt`

- [ ] **Step 1: Create EnhancedInputAction golden fixture**

```text
Begin Object Class="/Script/BlueprintGraph.K2Node_Event" Name="K2Node_Event_0"
   NodeGuid=11111111111111111111111111111111
   NodeComment=""
   Pin: then (Exec) LinkedTo=(22222222)
   CustomProperties Pin: PinName="EnhancedInputActionValue" PinType=() IsArray=False IsRef=False
End Object
```

- [ ] **Step 2: Create Interface Call golden fixture**

```text
Begin Object Class="/Script/BlueprintGraph.K2Node_CallInterfaceFunction" Name="K2Node_CallInterfaceFunction_0"
   NodeGuid=33333333333333333333333333333333
   NodeComment=""
   Pin: execute (Exec) LinkedTo=(44444444)
   Pin: self (Object) LinkedTo=(55555555)
   Pin: ReturnValue (Float) LinkedTo=(66666666)
   CustomProperties Pin: PinName="ReturnValue" PinType=(PinCategory="float") IsArray=False IsRef=False
End Object
```

- [ ] **Step 3: Create Macro golden fixture**

```text
Begin Object Class="/Script/BlueprintGraph.K2Node_MacroInstance" Name="K2Node_MacroInstance_0"
   NodeGuid=77777777777777777777777777777777
   NodeComment=""
   MacroGraphName="ForEachLoop"
   Pin: then_0 (Exec) LinkedTo=(88888888)
   Pin: ArrayElement (Object) LinkedTo=(99999999)
   Pin: ArrayIndex (Int) LinkedTo=(aaaaaaaa)
End Object
```

- [ ] **Step 4: Create Delegate golden fixture**

```text
Begin Object Class="/Script/BlueprintGraph.K2Node_Event" Name="K2Node_Event_Delegate"
   NodeGuid=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
   NodeComment=""
   Pin: then (Exec) LinkedTo=(cccccccc)
   CustomProperties Pin: PinName="DelegateOutput" PinType=(PinCategory="delegate") IsArray=False IsRef=False
End Object
```

- [ ] **Step 5: Verify fixtures load correctly**

Run: `python -c "from pathlib import Path; d=Path('tests/fixtures/ue_editor_blueprint_text'); [print(f'{f.name}: {len(f.read_text())} bytes') for f in sorted(d.glob('*.txt'))]"`
Expected: All 9 fixture files listed with non-zero sizes

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/ue_editor_blueprint_text/
git commit -m "test: add golden fixtures for EnhancedInputAction, InterfaceCall, Macro, Delegate"
```

---

### Task 7: Add golden fixture structure tests

**Files:**
- Modify: `tests/test_blueprint_ue_golden.py:153` (after for_loop test)

- [ ] **Step 1: Add structure tests for new fixtures**

```python
def test_enhanced_input_action_golden_structure():
    """验证 enhanced_input_action.txt golden fixture 结构。"""
    golden = load_golden("enhanced_input_action.txt")
    assert 'Class="/Script/BlueprintGraph.K2Node_Event"' in golden
    assert "NodeGuid=11111111111111111111111111111111" in golden
    assert "Pin: then (Exec)" in golden
    assert "EnhancedInputActionValue" in golden


def test_interface_call_golden_structure():
    """验证 interface_call.txt golden fixture 结构。"""
    golden = load_golden("interface_call.txt")
    assert 'Class="/Script/BlueprintGraph.K2Node_CallInterfaceFunction"' in golden
    assert "NodeGuid=33333333333333333333333333333333" in golden
    assert "Pin: ReturnValue (Float)" in golden


def test_macro_golden_structure():
    """验证 macro.txt golden fixture 结构。"""
    golden = load_golden("macro.txt")
    assert 'Class="/Script/BlueprintGraph.K2Node_MacroInstance"' in golden
    assert "MacroGraphName=ForEachLoop" in golden
    assert "Pin: ArrayElement (Object)" in golden
    assert "Pin: ArrayIndex (Int)" in golden


def test_delegate_golden_structure():
    """验证 delegate.txt golden fixture 结构。"""
    golden = load_golden("delegate.txt")
    assert 'Class="/Script/BlueprintGraph.K2Node_Event"' in golden
    assert "DelegateOutput" in golden
    assert 'PinCategory="delegate"' in golden
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/test_blueprint_ue_golden.py -v`
Expected: All tests pass (existing + 4 new)

- [ ] **Step 3: Commit**

```bash
git add tests/test_blueprint_ue_golden.py
git commit -m "test: add golden structure tests for 4 new node types"
```

---

### Task 8: Harden repr-free fallback in `_format_ue_value`

**Files:**
- Modify: `src/uasset_read/renderers/blueprint_ue_renderer.py:111-112`

- [ ] **Step 1: Replace `str(value)` fallback with explicit type handling**

Replace lines 111-112:

```python
    # Fallback: 避免 Python repr（ClassName(...) 或 <object at 0x...>）
    # 对未知类型使用安全的字符串表示
    if hasattr(value, '__dict__'):
        # dataclass 或普通对象 → 展开为 Key=Value 对
        parts = [f"{k}={_format_ue_value(v)}" for k, v in value.__dict__.items()]
        return "(" + ",".join(parts) + ")"
    return _escape_ue_value(str(value))
```

- [ ] **Step 2: Add test for unknown type fallback**

Add to `tests/test_blueprint_ue_golden.py`:

```python
def test_unknown_type_fallback_no_repr():
    """测试未知类型的 fallback 不产生 Python repr。"""
    class CustomType:
        def __init__(self):
            self.x = 1
            self.y = 2
    result = _format_ue_value(CustomType())
    assert "0x" not in result  # 无内存地址
    assert "object" not in result.lower()  # 无 object at ...
    assert "StructValue" not in result  # 无 ClassName(...) repr
    assert "x=1" in result  # 应展开为 Key=Value 对
    assert "y=2" in result
```

- [ ] **Step 3: Run test**

Run: `python -m pytest tests/test_blueprint_ue_golden.py::test_unknown_type_fallback_no_repr -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/uasset_read/renderers/blueprint_ue_renderer.py tests/test_blueprint_ue_golden.py
git commit -m "fix: harden repr-free fallback in _format_ue_value for unknown types"
```

---

### Task 9: Add blueprint_text vs blueprint_ue_text docstring

**Files:**
- Modify: `src/uasset_read/renderers/blueprint_text_renderer.py:32-35`
- Modify: `src/uasset_read/renderers/blueprint_ue_renderer.py:115-118`

- [ ] **Step 1: Add differentiation docstring to BlueprintTextRenderer**

```python
class BlueprintTextRenderer(IRenderer):
    """蓝图文本格式渲染器 — 执行链 + 反编译函数摘要。

    与 blueprint_ue_text 的区别：
    - blueprint_text: 输出执行链、反编译 C++ 函数、紧凑节点列表（短类型名）
    - blueprint_ue_text: 模拟 UE 编辑器 Ctrl+C 格式（Begin Object / CustomProperties Pin）
    """
```

- [ ] **Step 2: Add differentiation docstring to BlueprintUERenderer**

```python
class BlueprintUERenderer(IRenderer):
    """模拟 UE 编辑器 Ctrl+C 复制的蓝图文本格式。

    与 blueprint_text 的区别：
    - blueprint_ue_text: 输出 Begin Object / End Object 块、CustomProperties Pin、LinkedTo 引用
    - blueprint_text: 输出执行链、反编译函数、紧凑节点列表

    输出应避免 Python repr（如 StructValue(...)、TextValue(...)），
    所有值通过 _format_ue_value() 格式化为 UE 风格字符串。
    """
```

- [ ] **Step 3: Run test**

Run: `python -m pytest tests/test_blueprint_ue_golden.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/uasset_read/renderers/blueprint_text_renderer.py src/uasset_read/renderers/blueprint_ue_renderer.py
git commit -m "docs: add blueprint_text vs blueprint_ue_text differentiation docstrings"
```

---

### Task 10: Full test suite verification

- [ ] **Step 1: Run full test suite**

Run: `python scripts/test_matrix.py smoke`
Expected: 100% pass rate

- [ ] **Step 2: Run quality gate**

Run: `python scripts/test_matrix.py quality`
Expected: All quality gates pass
