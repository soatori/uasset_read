---
phase: 056
name: C++ 类骨架提取
type: plan
waves: 4
depends_on: []
files_modified:
  - src/uasset_read/cpp_gen/__init__.py
  - src/uasset_read/cpp_gen/cpp_type_mapper.py
  - src/uasset_read/cpp_gen/cpp_uproperty_mapper.py
  - src/uasset_read/cpp_gen/extract_cpp_skeleton.py
  - src/uasset_read/cpp_gen/formatters/cpp_json_ir.py
  - src/uasset_read/cpp_gen/formatters/cpp_header_formatter.py
  - src/uasset_read/cli.py
  - tests/test_cpp_type_mapper.py
  - tests/test_cpp_uproperty_mapper.py
  - tests/test_extract_cpp_skeleton.py
  - tests/test_cpp_header_formatter.py
  - tests/test_cpp_skeleton_e2e.py
autonomous: true
requirements: [CPP-01, CPP-02, CPP-03]
---

# Phase 56: C++ 类骨架提取 — PLAN.md

**Goal**: 从蓝图 PackageSummary、ExportMap 和组件/变量数据导出完整的 C++ 类声明骨架，包括继承链、组件 UPROPERTY 和变量 UPROPERTY。输出为结构化 JSON IR + .h 文本。

**Requirements**: CPP-01, CPP-02, CPP-03

## Success Criteria (from ROADMAP)

1. 运行 CLI 后，输出的 C++ 类声明包含完整父类继承链（如 `class AMyCharacter : public ACharacter`）
2. 所有蓝图组件均生成了 UPROPERTY 声明，包含正确的指针类型、变量名和可见性标记
3. 所有蓝图变量均生成了 UPROPERTY 声明，包含正确的 C++ 类型名、默认值和 Blueprint 可见性标记
4. 生成的 .h 骨架文件可直接作为 C++ 头文件模板使用

## Wave Structure

```
Wave 1: 56-01 — 类型映射 + CPF 映射 (基础模块)
    │
Wave 2: 56-02 — 骨架提取 + JSON IR (核心逻辑)
    │
Wave 3: 56-03 — 头文件格式化 (文本输出)
    │
Wave 4: 56-04 — CLI 集成 + 真实 .uasset 端到端测试
```

## Decisions (LOCKED from 056-CONTEXT.md)

| ID | Decision |
|----|----------|
| D-01 | JSON IR 中间表示，`cpp_class` 含 header_meta/properties/methods/constructor |
| D-02 | 混合策略继承链 — PackageLinker ClassParent 追溯 + 内置引擎类映射表 |
| D-03 | 核心类型硬编码 + scripts/generate_cpp_types.py 扩展脚本 |
| D-04 | CPF 标志直接映射到 UPROPERTY 标记 |
| D-05 | 完整 UE 头文件模板 + JSON IR 结构化字段 |
| D-06 | 模块化子结构 JSON（见 CONTEXT.md 示例） |
| D-07 | Golden-path 集成测试基于 BP_FirstPersonCharacter 真实导出 JSON（通过 `parse_uasset_with_linker`） |

---

## Wave 1: 类型映射 + CPF 映射

详见 [`56-01-PLAN.md`](56-01-PLAN.md)

**产出**:
- `src/uasset_read/cpp_gen/cpp_type_mapper.py` — `UE_TO_CPP_TYPE_MAP`, `ENGINE_CLASS_PATHS`, `ue_path_to_cpp_type()`, `ue_package_path_to_cpp_class()`
- `src/uasset_read/cpp_gen/cpp_uproperty_mapper.py` — `CPF_TO_UPROPERTY_MAP`, `cpf_flags_to_uproperty_marks()`
- `tests/test_cpp_type_mapper.py`
- `tests/test_cpp_uproperty_mapper.py`

**验证**: `pytest tests/test_cpp_type_mapper.py tests/test_cpp_uproperty_mapper.py -v -x`

---

## Wave 2: 骨架提取 + JSON IR

详见 [`56-02-PLAN.md`](56-02-PLAN.md)

**产出**:
- `src/uasset_read/cpp_gen/extract_cpp_skeleton.py` — `extract_cpp_class_skeleton(LinkerParseResult) -> CppClassIR`
- `src/uasset_read/cpp_gen/formatters/cpp_json_ir.py` — `CppClassIR`, `CppProperty`, `CppHeaderMeta` dataclasses + `format_cpp_class_json()`
- `tests/test_extract_cpp_skeleton.py`

**验证**: `pytest tests/test_extract_cpp_skeleton.py -v -x`

---

## Wave 3: 头文件格式化

详见 [`56-03-PLAN.md`](56-03-PLAN.md)

**产出**:
- `src/uasset_read/cpp_gen/formatters/cpp_header_formatter.py` — `format_cpp_header(ir) -> str`
- `tests/test_cpp_header_formatter.py`

**验证**: `pytest tests/test_cpp_header_formatter.py -v -x`

---

## Wave 4: CLI 集成 + 真实 .uasset 端到端测试

> **FIX**: 修复 plan-checker 发现的两项 blocker — CLI 集成缺失 + golden-path 使用 mock 而非真实 .uasset。

### Task 4-1: CLI 集成

**File**: `src/uasset_read/cli.py`

在现有 argparse 中添加 `--cpp-skeleton` 输出模式：

```python
# 在 cli.py 的 output format 参数中添加
parser.add_argument("--cpp-skeleton", action="store_true",
                    help="Output C++ class skeleton (.h header) instead of JSON")
```

**集成逻辑**（在 `parse_uasset_with_linker` 调用之后）：

```python
if args.cpp_skeleton:
    from uasset_read.cpp_gen import extract_cpp_class_skeleton, format_cpp_header
    ir = extract_cpp_class_skeleton(linker_result)
    output = format_cpp_header(ir)
    # 写入文件或 stdout
```

同时更新 `src/uasset_read/cpp_gen/__init__.py` 导出：
```python
__all__ = [
    "ue_path_to_cpp_type",
    "ue_package_path_to_cpp_class",
    "cpf_flags_to_uproperty_marks",
    "extract_cpp_class_skeleton",
    "format_cpp_header",
    "format_cpp_class_json",
    "CppClassIR",
]
```

**验证**:
```bash
uasset-read BP_FirstPersonCharacter.uasset --cpp-skeleton | grep -c "UPROPERTY"
# 应输出 ≥ 3 (至少 3 个 UPROPERTY 声明)
```

### Task 4-2: 真实 .uasset 端到端测试

**File**: `tests/test_cpp_skeleton_e2e.py`

> **FIX**: 不再使用 mock `LinkerParseResult`，而是通过 `parse_uasset_with_linker` 从真实 `.uasset` 文件驱动完整管线。

```python
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset_with_linker
from uasset_read.cpp_gen import extract_cpp_class_skeleton, format_cpp_header

UASSET_DIR = Path(r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson")

class TestBPFirstPersonCharacterRealUasset:
    """Golden-path: real .uasset → parse_uasset_with_linker → extract → format → .h"""

    @pytest.fixture
    def bp_first_person_uasset(self):
        """Locate BP_FirstPersonCharacter.uasset in sample directory."""
        candidates = list(UASSET_DIR.rglob("BP_FirstPersonCharacter.uasset"))
        assert len(candidates) > 0, f"BP_FirstPersonCharacter.uasset not found in {UASSET_DIR}"
        return candidates[0]

    @pytest.fixture
    def linker_result(self, bp_first_person_uasset):
        """Parse real .uasset file through full pipeline."""
        return parse_uasset_with_linker(str(bp_first_person_uasset))

    def test_class_name_and_parent(self, linker_result):
        ir = extract_cpp_class_skeleton(linker_result)
        assert "Character" in ir.parent_class or ir.parent_class == "ACharacter"
        assert "FirstPerson" in ir.name or "BP" in ir.name

    def test_component_uproperties(self, linker_result):
        ir = extract_cpp_class_skeleton(linker_result)
        comp_props = [p for p in ir.properties if p.category == "component"]
        assert len(comp_props) >= 2, "Expected at least 2 component properties"
        # All components should be pointer types
        for prop in comp_props:
            assert prop.cpp_type.endswith("*"), f"{prop.name} should be pointer type"
            assert "Instanced" in prop.uproperty_marks

    def test_variable_uproperties(self, linker_result):
        ir = extract_cpp_class_skeleton(linker_result)
        var_props = [p for p in ir.properties if p.category == "variable"]
        # May be 0 if blueprint has no SVarTable entries — just verify format
        for prop in var_props:
            assert prop.cpp_type in ("float", "bool", "int32", "FName", "FString", "FVector", "FRotator")

    def test_header_output(self, linker_result):
        ir = extract_cpp_class_skeleton(linker_result)
        header = format_cpp_header(ir)
        assert "#pragma once" in header
        assert "GENERATED_BODY()" in header
        assert ".generated.h" in header
        assert "UCLASS" in header
        assert "UPROPERTY" in header
        assert ": public" in header  # inheritance
```

**边界测试**（使用 mock 数据即可）：
```python
class TestCPPSkeletonBoundaryCases:
    """Boundary tests using mock data — empty classes, no components, etc."""

    def test_empty_blueprint(self):
        """Empty blueprint produces minimal valid .h."""
        ir = CppClassIR(
            name="AMinimalClass",
            parent_class="AActor",
            header_meta=CppHeaderMeta(),
            properties=[],
            methods=[],
            constructor={}
        )
        header = format_cpp_header(ir)
        assert "#pragma once" in header
        assert "class AMinimalClass : public AActor" in header

    def test_single_inheritance(self):
        ir = CppClassIR(
            name="UBP_Test",
            parent_class="UActorComponent",
            header_meta=CppHeaderMeta(),
            properties=[],
            methods=[],
            constructor={}
        )
        header = format_cpp_header(ir)
        assert "class UBP_Test : public UActorComponent" in header
```

**验证**: `pytest tests/test_cpp_skeleton_e2e.py -v -x`

---

## Dependency Graph

```
56-01 (类型映射 + CPF映射) ──→ 56-02 (骨架提取 + JSON IR) ──→ 56-03 (头文件格式化) ──→ 56-04 (CLI集成 + 端到端测试)
```

## Requirements Coverage

| Requirement | Wave | Status |
|-------------|------|--------|
| CPP-01 (继承链) | 56-02 | Covered — `ue_package_path_to_cpp_class()` walks ClassParent chain |
| CPP-02 (组件 UPROPERTY) | 56-01, 56-02, 56-03 | Covered — type mapper + CPF mapper + skeleton extraction + header formatter |
| CPP-03 (变量 UPROPERTY) | 56-01, 56-02, 56-03 | Covered — same pipeline as CPP-02 |

## Decisions Coverage

| Decision | Wave | Status |
|----------|------|--------|
| D-01 (JSON IR) | 56-02 | `CppClassIR.to_dict()` outputs exact structure |
| D-02 (混合继承链) | 56-01, 56-02 | `ENGINE_CLASS_PATHS` + `ue_package_path_to_cpp_class()` |
| D-03 (混合类型映射) | 56-01 | `UE_TO_CPP_TYPE_MAP` hardcoded dict (extension script deferred) |
| D-04 (CPF→UPROPERTY) | 56-01 | `CPF_TO_UPROPERTY_MAP` + `cpf_flags_to_uproperty_marks()` |
| D-05 (完整UE头文件) | 56-02, 56-03 | `CppHeaderMeta` + `format_cpp_header()` |
| D-06 (JSON IR 结构) | 56-02 | `CppClassIR` dataclass matches D-06 example |
| D-07 (Golden-path 测试) | 56-04 | `parse_uasset_with_linker` on real `.uasset` → `extract_cpp_class_skeleton` → `format_cpp_header` |

## New Module Structure

```
src/uasset_read/cpp_gen/
├── __init__.py                  # exports all public symbols
├── cpp_type_mapper.py           # D-03: UE path → C++ type mapping
├── cpp_uproperty_mapper.py      # D-04: CPF → UPROPERTY mapping
├── extract_cpp_skeleton.py      # Core: LinkerParseResult → CppClassIR
└── formatters/
    ├── __init__.py
    ├── cpp_json_ir.py           # D-01/D-06: CppClassIR + JSON formatter
    └── cpp_header_formatter.py  # D-05: .h text output

tests/
├── test_cpp_type_mapper.py
├── test_cpp_uproperty_mapper.py
├── test_extract_cpp_skeleton.py
├── test_cpp_header_formatter.py
└── test_cpp_skeleton_e2e.py     # Real .uasset golden-path + boundary tests
```

## Verification Checklist

- [ ] `pytest tests/test_cpp_type_mapper.py tests/test_cpp_uproperty_mapper.py -v -x`
- [ ] `pytest tests/test_extract_cpp_skeleton.py -v -x`
- [ ] `pytest tests/test_cpp_header_formatter.py -v -x`
- [ ] `pytest tests/test_cpp_skeleton_e2e.py -v -x`
- [ ] `uasset-read <real.uasset> --cpp-skeleton` produces valid .h text with UPROPERTY declarations
- [ ] No new runtime dependencies (pip check passes)
- [ ] All 3 success criteria from ROADMAP met (CLI output, component UPROPERTY, variable UPROPERTY)
