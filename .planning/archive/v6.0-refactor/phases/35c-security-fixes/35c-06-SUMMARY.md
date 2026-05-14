---
title: "35c-06: property_types.py 属性条目计数验证"
plan_id: "35c-06"
phase: "35c"
subsystem: "parsers"
tags: [security, validation, property-types]
requires: []
provides: [HIGH-07-fix]
affects: [property_types.py]
tech-stack:
  added: [count-validation]
  patterns: [defensive-validation]
key-files:
  created: []
  modified: [src/uasset_read/parsers/property_types.py]
decisions:
  - 使用统一的 MAX_PROPERTY_COUNT (10,000) 限制所有集合类型
  - 验证在计数读取后立即进行，失败时抛 ParseError
metrics:
  duration: "5 min"
  completed_date: "2026-05-13"
  tasks_completed: 1
  files_modified: 1
---

# Phase 35c Plan 06: property_types.py 属性条目计数验证 Summary

为 ArrayProperty、MapProperty、SetProperty 添加条目计数验证，防止恶意文件分配过大内存（HIGH-07 安全修复）。

## 修改内容

### 1. parse_array_property (line 109)

```python
count = archive.read_i32()
if count < 0 or count > MAX_PROPERTY_COUNT:
    raise ParseError(
        f"ArrayProperty count {count} out of range [0, {MAX_PROPERTY_COUNT}]"
    )
```

### 2. parse_map_property (line 183)

```python
num_entries = archive.read_i32()
if num_entries < 0 or num_entries > MAX_PROPERTY_COUNT:
    raise ParseError(
        f"MapProperty entries count {num_entries} out of range [0, {MAX_PROPERTY_COUNT}]"
    )
```

### 3. parse_set_property (line 203)

```python
num_elements = archive.read_i32()
if num_elements < 0 or num_elements > MAX_PROPERTY_COUNT:
    raise ParseError(
        f"SetProperty elements count {num_elements} out of range [0, {MAX_PROPERTY_COUNT}]"
    )
```

## 验收结果

- ✅ 负数计数抛 ParseError
- ✅ 超过 MAX_PROPERTY_COUNT (10,000) 的计数抛 ParseError
- ✅ 正常计数不受影响
- ✅ 属性相关测试全部通过（80 passed, 3 skipped）

## 测试执行

```bash
python -m pytest tests/ -k "property" -v
# 80 passed, 3 skipped, 414 deselected in 0.25s
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — this fix mitigates HIGH-07 (DoS via unbounded collection parsing).