# Phase 47: Pin LinkedTo 修复 — DISCUSSION-LOG.md

**Date:** 2026-05-15

## 讨论记录

### 1. 修复策略

**问题:** FEdGraphPinType 字段缺失/顺序错误导致 ~4 字节偏移

**选项:**
- 修正字段顺序和缺失字段 ← **选择**
- 先做二进制诊断确认
- 两者结合

**决策:** 直接修正 FEdGraphPinType 字段顺序和缺失字段。严格对照 UE 5.7 EdGraphPin.cpp。

### 2. 布尔序列化方式

**问题:** UE5 bool 序列化用 read_bool() 还是 read_bool_1byte()

**选项:**
- archive.py 新增 read_bool_ue5()
- 直接用 read_u8() != 0

**决策:** 用户明确要求"严禁直接读取字节，寻找编辑器源码的加载方式"。使用 `read_bool()` (4-byte uint32) 对齐 UE FArchive::operator<<(bool&) 行为。不需要 UE4 兼容。

### 3. 验证范围

**问题:** 只修 graph.py 还是也修 PropertyTag

**选项:**
- 只修 graph.py ← **选择**
- 同时修 PropertyTag
- 分多 phase

**决策:** 分多 phase 逐步修正。Phase 47 只修 FEdGraphPinType/UEdGraphPin 序列化。

### 4. UE 源码参考

**决策:** 使用本地 UE5.7 源码: `E:/Develop/lib/UnrealEngine/Engine/Source/`

## 关键发现

通过阅读 UE 5.7 EdGraphPin.cpp，发现当前 `read_ed_graph_pin_type()` 存在严重字段顺序不匹配：

1. `bIsReference` 和 `bIsWeakPointer` 使用 `read_bool_1byte()` (1B) 而非 `read_bool()` (4B)
2. 缺少 `bIsConst`, `bIsUObjectWrapper`, `bSerializeAsSinglePrecisionFloat` 字段
3. 字段顺序与 UE 源码 L163-345 不一致

总偏移约 -6 到 -9 字节，导致后续 `linked_to` 数组读取位置错误。
