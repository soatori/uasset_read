---
plan_id: 72-01
phase: 72
status: complete
date: 2026-05-23
---

# Plan 72-01: Pin 连接修复 — Summary

## Objective

修复 Phase 72-A 诊断确认的 2 个 Pin 序列化 bug。

## What was built

### Bug 1: history_type signed 转换

**文件:** `src/uasset_read/serializers/graph.py` L381, L433

**修复:** `read_u8()` 返回 255 时转换为 -1（signed int8）。

```python
history_type_raw = archive.read_u8()
history_type = history_type_raw - 256 if history_type_raw >= 128 else history_type_raw
```

**影响:** PinFriendlyName 和 DefaultTextValue 的 FText 解析，0xFF 正确映射为 None (-1)。

### Bug 2: ParentPin 条件读取

**文件:** `src/uasset_read/serializers/graph.py` L459-481

**修复:** `null != 0` 时只读 8B (null + owning)，`null == 0` 时读 24B (+ guid)。ReferencePassThrough 同步相同模式。

**影响:** ParentPin null 时不再多消费 16B GUID，后续 RefPassThrough/PersistentGuid/BitField 字段正确对齐。

## Test results

762 passed, 77 skipped, 1 pre-existing failure (Phase 71 execution_flows deprecation — unrelated).

## Key files created/modified

- `src/uasset_read/serializers/graph.py` — 2 bugs fixed

## Self-Check: PASSED
