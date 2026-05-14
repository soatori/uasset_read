# Phase 35e 补充计划 — 遗漏的布尔值序列化问题

**日期：** 2026-05-14
**来源：** Phase 35e 执行后深度审查发现

---

## 1. 问题概述

Phase 35e 修复了 3 个核心问题（D1: DefaultTextValue FText、D2: bSerializeAsSinglePrecisionFloat、D3: bIsUObjectWrapper），但审查发现 **所有新增/修改的布尔值字段仍然使用 `read_bool()`（4 字节）而非 `read_bool_ue5()`（1 字节）**。

这会导致在 UE5 文件中产生**额外的字节偏移累积**，可能完全抵消 D1/D2/D3 的修复效果。

---

## 2. 发现的问题

### 2.1 FEdGraphPinType 中的布尔值（graph.py）

| 行号 | 字段 | 当前代码 | 应为 | 偏移差 |
|------|------|---------|------|--------|
| 104 | b_is_map | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |
| 105 | b_is_set | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |
| 106 | b_is_array | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |
| 117 | is_reference | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |
| 118 | is_weak_pointer | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |
| 130 | is_const | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |
| 136 | is_uobject_wrapper | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |
| 142 | b_serialize_as_single_precision_float | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |

**累计偏移：最多 +24 字节**（8 个布尔值 × 3 字节差）

**UE 源码验证：** EdGraphPin.cpp L248-252：
```cpp
bool bIsReferenceBool = bIsReference;
bool bIsWeakPointerBool = bIsWeakPointer;
Ar << bIsReferenceBool;    // bool = 1 byte
Ar << bIsWeakPointerBool;  // bool = 1 byte
```

### 2.2 FMemberReference 中的布尔值（graph.py）

| 行号 | 字段 | 当前代码 | 应为 | 偏移差 |
|------|------|---------|------|--------|
| 566 | b_self_context | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |
| 567 | _b_was_deprecated | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |

**累计偏移：+6 字节**

**UE 源码验证：** MemberReference.h L74-95：
```cpp
mutable bool bSelfContext;      // 1 byte
mutable bool bWasDeprecated;    // 1 byte
```

### 2.3 K2Node 中的布尔值（graph.py）

| 行号 | 字段 | 当前代码 | 应为 | 偏移差 |
|------|------|---------|------|--------|
| 589 | b_defaults_to_pure | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |
| 604 | b_override_function | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |

**累计偏移：+6 字节**

### 2.4 FText 中的布尔值（graph.py）

| 行号 | 字段 | 当前代码 | 应为 | 偏移差 |
|------|------|---------|------|--------|
| 221 | b_has_culture | `read_bool()` (4B) | `read_bool_ue5()` (1B) | +3B |

**注意：** 这个已经在 Phase 35e 的 D1 修复中处理了（注释已说明 UE 用 uint32），但需要确认 UE5 资产是否确实用 1 字节。

---

## 3. 总偏移影响

| 区域 | 布尔值数量 | 总偏移差 |
|------|-----------|---------|
| FEdGraphPinType | 8 | +24B |
| FMemberReference | 2 | +6B |
| K2Node_CallFunction | 1 | +3B |
| K2Node_Event | 1 | +3B |
| FText (history_type=-1) | 1 | +3B |
| **总计** | **13** | **+39B** |

**这意味着即使 D1/D2/D3 修复了约 12 字节的偏移，仍有最多 39 字节的额外偏移未被修复。**

---

## 4. 修复方案

### 4.1 原则

所有 UE5 文件（`summary.file_version_ue5 > 0`）中的布尔值应使用 `read_bool_ue5()`（1 字节），UE4 文件继续使用 `read_bool()`（4 字节）。

### 4.2 修复清单

| 任务 | 文件 | 行号 | 修改 |
|------|------|------|------|
| 35e-S1 | graph.py | 104-106 | legacy container bools 加版本条件 |
| 35e-S2 | graph.py | 117-118 | is_reference/is_weak_pointer 加版本条件 |
| 35e-S3 | graph.py | 130 | is_const 加版本条件 |
| 35e-S4 | graph.py | 136 | is_uobject_wrapper 加版本条件 |
| 35e-S5 | graph.py | 142 | b_serialize_as_single_precision_float 加版本条件 |
| 35e-S6 | graph.py | 566-567 | FMemberReference bools 加版本条件 |
| 35e-S7 | graph.py | 589 | b_defaults_to_pure 加版本条件 |
| 35e-S8 | graph.py | 604 | b_override_function 加版本条件 |
| 35e-S9 | graph.py | 221 | b_has_culture 确认 UE5 行为 |

### 4.3 修复模式

```python
# 修复前
pin_type.is_reference = archive.read_bool()

# 修复后
if summary.file_version_ue5 > 0:
    pin_type.is_reference = archive.read_bool_ue5()
else:
    pin_type.is_reference = archive.read_bool()
```

或使用辅助函数：
```python
def _read_bool_for_version(archive, summary):
    if summary.file_version_ue5 > 0:
        return archive.read_bool_ue5()
    return archive.read_bool()
```

---

## 5. 验证方案

### 5.1 单元测试

为每个修复的布尔值编写测试：
- 验证 UE4 文件使用 4 字节读取
- 验证 UE5 文件使用 1 字节读取
- 验证修复后字段值正确

### 5.2 集成测试

- 运行现有测试套件
- 验证 linked_to_raw 非空
- 验证 execution_flows/data_flows 完整构建
- 使用二进制跟踪工具验证零偏移

### 5.3 回归测试

- 确保 UE4 资产解析不受影响
- 确保 UE5 资产解析结果正确

---

## 6. 与 v6.5 里程碑的关系

这些补充修复应纳入 v6.5 里程碑的 **Phase 37（UEdGraphPin 布尔值序列化修正）**，作为该阶段的扩展范围。

| v6.5 Phase | 原范围 | 补充范围 |
|------------|--------|---------|
| Phase 37 | UEdGraphPin 布尔值修正 | + FEdGraphPinType/FMemberReference/K2Node 布尔值修正 |

---

## 7. 风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| UE4/UE5 版本判断错误 | 低 | 高 | 双版本测试 |
| 某些 UE5 文件仍用 4 字节 | 中 | 中 | CustomVersion 检查 |
| 修复后仍有偏移 | 低 | 高 | 二进制跟踪验证 |

---

*发现日期: 2026-05-14*
*来源: Phase 35e 执行后深度审查*
*状态: 待执行*
