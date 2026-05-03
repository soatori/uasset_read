# Phase 17: 属性解析修复 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 17-property-parsing-fix
**Areas discussed:** 属性标签格式验证, serial_offset 数据布局, 错误处理策略, 未知类型处理

---

## 属性标签格式验证

通过 UE 5.7 源码对比，定位两个根因：

1. **版本阈值不一致**：代码使用 `PROPERTY_TAG_COMPLETE_TYPE_NAME = 1000`，UE 源码正确值为 `1012`。但影响有限，因为 UE 5.7 (1017) > 两者。

2. **PROP_TAG_HAS_EXTENSIONS (0x04) 未处理**：代码已定义常量但注释 "defer to Phase 3" 未实现。当 flags & 0x04 = 1 时跳过扩展数据读取，导致位置错位。

**验证文件：**
- `PropertyTag.cpp` 第 541-544 行
- `Class.cpp` 第 1627-1654 行

**Notes:** 用户选择需要更多 UE 源码对比后确认发现。

---

## serial_offset 数据布局

通过 UE 源码验证发现：

| 发现 | UE 源码位置 |
|------|-------------|
| ScriptSerializationStartOffset 是相对于 SerialOffset 的偏移 | `ObjectResource.h` 第 280-285 行注释 |
| UE5 >= 1010 序列化 ScriptSerializationOffset 字段 | `ObjectResource.cpp` 第 212-222 行 |
| UE5 >= 1011 需要读取 SerializationControlExtensions 头部 | `Class.cpp` 第 1627-1654 行 |

**代码错误：** `parse_properties_from_export()` 第 4343 行直接使用 `serial_offset`，应使用 `serial_offset + script_serial_offset` 并先读取头部。

**Notes:** 用户确认需要更多源码对比后，完整验证了数据布局流程。

---

## 错误处理策略

| Option | Description | Selected |
|--------|-------------|----------|
| 跳过单个属性（当前） | 遇到错误时跳过当前属性，继续解析下一个 | |
| 智能恢复 | 根据 Size 字段跳到下一个属性 | |
| 立即中断（保守） | 错误后立即中断，确保数据一致性 | |
| **分层策略** | 三结合：尝试恢复 → 失败则跳过 → 严重错误则中断 | ✓ |

**User's choice:** 分层策略（推荐）
**Notes:** 分层策略提供最大数据提取能力同时保持健壮性。

---

## 未知类型处理

| Option | Description | Selected |
|--------|-------------|----------|
| **存储原始数据** | 读取 Size 字节并存储为原始数据，继续解析 | ✓ |
| 跳过并记录 | 跳过未知类型属性，记录警告 | |
| 中断解析 | 未知类型视为错误，中断属性解析 | |

**User's choice:** 存储原始数据（推荐）
**Notes:** 存储原始数据确保不丢失信息，便于后续分析和调试。

---

## Claude's Discretion

None — 所有决策都通过讨论确定。

---

## Deferred Ideas

None — 讨论保持在 Phase 17 范围内。

---
*Phase: 17-property-parsing-fix*
*Discussion log created: 2026-05-03*