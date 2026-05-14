---
phase: "35d"
plan: "03"
subsystem: "models"
tags: ["CR-13", "properties", "default-values", "tdd"]
commit_hashes:
  test: "262f2ec"
  feat: "b4d49f8"
  refactor: "fdd623e"
duration: "~25 min"
completed_date: "2026-05-13"
requires: []
provides: ["property_type default values on Value subclasses"]
affects: ["src/uasset_read/models/properties.py", "src/uasset_read/parsers/property_types.py", "tests/test_phase35d_model_class_fixes.py", "tests/test_phase13_transform.py"]
tech_stack:
  added: ["dataclass inheritance (non-dataclass base)"]
  patterns: ["TDD RED/GREEN/REFACTOR", "default field values avoiding ordering issues"]
key_files:
  created:
    - "tests/test_phase35d_model_class_fixes.py"
  modified:
    - "src/uasset_read/models/properties.py"
    - "src/uasset_read/parsers/property_types.py"
    - "tests/test_phase13_transform.py"
decisions:
  - "Convert AdvancedPropertyValue from dataclass to plain class to avoid Python dataclass field ordering issues when adding defaults to inherited property_type field"
  - "Add property_type default to each Value subclass individually rather than using kw_only on the base class"
  - "Remove explicit property_type= from all callers (property_types.py, test_phase13_transform.py)"
  - "Keep backward compatibility: explicit property_type parameter still accepted"
---

# Phase 35d Plan 03: 模型类修复 — property_type 默认值 (CR-13)

## 概述

为 `StructValue`, `MapValue`, `SetValue`, `EnumValue`, `TextValue`, `DelegateValue` 六个 Value 子类添加默认 `property_type` 值，使调用者无需手动传入 `property_type`。

## TDD 执行记录

| 阶段 | Commit | 说明 |
|------|--------|------|
| RED | `262f2ec` | 17 个测试全部因 TypeError 失败 (missing property_type) |
| GREEN | `b4d49f8` | 修改 properties.py 后 17 个测试全部通过 |
| REFACTOR | `fdd623e` | 移除 callers 中的显式 property_type 参数，回归测试通过 |

## 技术细节

### 问题背景

`AdvancedPropertyValue` 基类定义了 `property_type: str`（无默认值），六个子类继承此字段。由于 Python dataclass 继承的字段顺序约束（父类字段在子类字段之前），无法直接在子类中添加有默认值的 `property_type` 而不破坏 `__init__` 签名。

### 解决方案

将 `AdvancedPropertyValue` 从 `@dataclass` 转换为普通 Python 类，使其不产生任何 dataclass 字段。然后在每个子类中单独添加 `property_type: str = "XXXProperty"` 字段：

```python
class AdvancedPropertyValue:
    """非 dataclass — 仅作为类型标识基类。"""
    pass

@dataclass
class StructValue(AdvancedPropertyValue):
    struct_type: str
    fields: Dict[str, Any] = field(default_factory=dict)
    property_type: str = "StructProperty"  # ✅ 有默认值
```

这样生成的 `__init__` 签名中 `struct_type`（无默认值）在前，`fields`（默认值）和 `property_type`（默认值）在后，符合 Python 的字段顺序约束。

### 默认值对照

| 子类 | 默认值 |
|------|--------|
| StructValue | `"StructProperty"` |
| MapValue | `"MapProperty"` |
| SetValue | `"SetProperty"` |
| EnumValue | `"EnumProperty"` |
| TextValue | `"TextProperty"` |
| DelegateValue | `"DelegateProperty"` |

## 验证

```bash
python -m pytest tests/test_phase35d_model_class_fixes.py -v  # 17 passed
python -m pytest tests/ -x -q  # 257 passed, 65 skipped (1 pre-existing failure)
```

## 已知问题

无。CR-13 完全解决。

## 自我检查

- [x] `tests/test_phase35d_model_class_fixes.py` 存在且 17 个测试全部通过
- [x] `src/uasset_read/models/properties.py` 中所有 6 个子类都有 `property_type: str = "XXXProperty"` 默认值
- [x] `src/uasset_read/parsers/property_types.py` 中无 `property_type=` 显式传参
- [x] `tests/test_phase13_transform.py` 中无 `property_type=` 显式传参
- [x] TDD gate: RED → GREEN → REFACTOR 三阶段提交存在
- [x] 无回归
