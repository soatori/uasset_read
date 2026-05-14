---
phase: 22-节点序列化修复
plan: 06
status: partial
completed: 2026-05-05
issues_resolved: 1
issues_remaining: 3
---

# Phase 22 Plan 06 Summary: 正确定位 pins_offset

## 执行状态

**状态**: Partial — FText 枚举值修正完成，但 Pin 解析仍有问题

## 关键发现

### 发现 1: ETextHistoryType 枚举值错误

**UE 源码验证（TextHistory.h L23-41）：**
```cpp
enum class ETextHistoryType : int8
{
    None = -1,      // int8 = -1, uint8 = 255
    Base = 0,       // ← 正确！history_type=0 是 Base，不是 None
    NamedFormat = 1,
    OrderedFormat = 2,
    ...
}
```

**原代码错误：**
- history_type=0 被当作 None（读取 bHasCultureInvariantString）
- history_type=255 被当作特殊 pattern（跳过 8 bytes）

**修正后：**
- history_type=255/-1 → None（读取 bHasCultureInvariantString + optional FString）
- history_type=0 → Base（读取 Namespace + Key + SourceString, 3 FStrings）

### 发现 2: SourceIndex 序列化位置错误

**UE 源码验证（EdGraphPin.cpp L1858-1868）：**
```cpp
#if WITH_EDITORONLY_DATA
    if (!Ar.IsFilterEditorOnly())
    {
        Ar << PinFriendlyName;  // FText
    }
#endif

if (Ar.CustomVer(FUE5MainStreamObjectVersion::GUID) >= FUE5MainStreamObjectVersion::EdGraphPinSourceIndex)
{
    Ar << SourceIndex;  // ← 在 PinFriendlyName 之后，PinToolTip 之前！
}

Ar << PinToolTip;
```

**原代码错误：**
- SourceIndex 在 PinToolTip 之后读取

**修正后：**
- SourceIndex 在 PinFriendlyName 之后读取

### 发现 3: Direction 后有 2 bytes 额外数据

**实测数据验证：**
- PinName (FName): offset 93357, index=149 → name_map[149]="execute" ✓
- PinFriendlyName (FText): offset 93365-93374 (9 bytes) ✓
- PinToolTip (UTF16CHAR empty): offset 93374-93380 (6 bytes) ✓
- Direction: offset 93380, value=0 (1 byte) ✓
- **额外数据**: offset 93381-93382 (2 bytes: 00 00) ✗
- PinType start: offset 93383 (正确应该是 offset 93381)

**假设：Direction 可能占用 2 bytes（uint16 或有 padding）**

尝试修改代码读取 2 bytes，但验证失败（PinCategory index 仍然为垃圾值）。

## 代码修改

### 已实现修改

| 文件 | 修改内容 |
|------|---------|
| uasset_read.py:2822-2873 | 修正 FText ETextHistoryType 枚举值处理 |
| uasset_read.py:2903-2931 | 修正 skip_ftext 函数的枚举值处理 |
| uasset_read.py:3008-3011 | 修正 SourceIndex 位置（在 PinFriendlyName 之后）|
| uasset_read.py:3016-3019 | 尝试 Direction 读取 2 bytes（待验证）|

### 未实现（需要后续 Phase）

| 问题 | 建议 |
|------|------|
| Direction 序列化格式 | 研究 UE 源码中 TEnumAsByte 的实际序列化大小 |
| PinType 版本检查 | read_ed_graph_pin_type 可能需要修正版本逻辑 |
| ContainerType 格式 | 可能 UE5 中 ContainerType 有新的序列化方式 |

## 测试结果

| 测试 | 修复前 | 修复后 | 说明 |
|------|--------|--------|------|
| TEST-01: K2Node 数量 | PASSED | PASSED | 保持不变 |
| TEST-02: execution_flows | FAILED | FAILED | Pin 解析问题未解决 |
| TEST-03: data_flows | FAILED | FAILED | Pin 解析问题未解决 |
| TEST-04: function_reference | PASSED | FAILED | 位置错乱导致新问题 |

## 下一步建议

### 建议 1: 研究 TEnumAsByte 序列化格式

需要确定：
- Direction (TEnumAsByte) 是否占用 uint8, uint16, 或 uint32
- 是否有 padding bytes
- UE5 中是否有版本依赖的变化

### 建议 2: 研究 PinType 序列化格式

需要确定：
- read_ed_graph_pin_type 的版本检查是否正确
- FFrameworkObjectVersion 和 FReleaseObjectVersion 的 GUID 是否正确
- UE5 中 PinType 是否有新的序列化方式

### 建议 3: 创建新 Phase 22-07

问题需要系统性调试：
- Phase 22-07: Direction 和 PinType 序列化格式修复
- 使用更精细的二进制分析和 UE 源码对比

## 手动验证参考

正确的 Pin 数据结构（部分字段验证）：

| Offset | 字段 | 值 | 状态 |
|--------|------|-----|------|
| 93357 | PinName index | 149 → "execute" | ✓ 正确 |
| 93365-93374 | PinFriendlyName (FText) | 9 bytes | ✓ 正确 |
| 93374-93380 | PinToolTip (UTF16CHAR) | 6 bytes | ✓ 正确 |
| 93380 | Direction | 0 | ? 可能只占 1 byte |
| 93381-93382 | 额外数据 | 00 00 | ✗ 未知字段 |
| 93383 | PinCategory index | 148 → "exec" | ✗ 应该在 93381 |

---
*Completed: 2026-05-05 — Phase 22-06 partial progress，FText 枚举值修正，Pin 解析仍需调试*