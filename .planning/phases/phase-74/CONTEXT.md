---
phase: 74
title: UE/CUE4Parse 对齐的 PinReference 主路径修复
status: Planned
created: 2026-05-25
---

# Phase 74 上下文

Phase 74 接续 Phase 73。Phase 73 建立了 Pin 字段级 trace、LinkedTo 恢复和端到端验收，但 `linkedto-read-failed-report.md` 仍显示核心问题不应继续靠扩大恢复窗口解决。最新 UE 源码与 CUE4Parse 对照表明，当前项目对 `SerializePin()` 的部分布局假设仍与真实实现不一致。

## 根因假设

UE/CUE4Parse 的真实规则：

- `SerializePinArray` 先读取 `int32 ArrayNum`。
- 每个元素调用 `SerializePin`。
- `SerializePin` 先读取 4 字节 bool `bNullPtr`。
- `bNullPtr == true` 时，只消费这个 bool，引用结束。
- `bNullPtr == false` 时，继续读取 `OwningNode` 和 `PinGuid`。
- 只有 `ResolveType == OwningNode` 时，才继续读取完整 `UEdGraphPin` body。
- `UEdGraphPin` body 从 `PinName` 开始，不重复序列化 `OwningNode + PinGuid`。

当前项目仍有 Phase 73 时代的兼容假设：owning pin body 会重复出现 `OwningNode + PinGuid`，并且部分 null 引用路径按更长结构处理。这会导致后续 `LinkedTo` count 在错误 offset 上读取。

## 源码依据

- UE: `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Private\EdGraph\EdGraphPin.cpp`
  - `FEdGraphPinType::Serialize`
  - `UEdGraphPin::Serialize`
  - `UEdGraphPin::SerializePinArray`
  - `UEdGraphPin::SerializePin`
- CUE4Parse:
  - `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Assets\Exports\EdGraph\UEdGraphPin.cs`
  - `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Assets\Exports\EdGraph\UEdGraphPinReference.cs`
  - `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\Engine\EdGraph\FEdGraphPinType.cs`
  - `E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Readers\FArchive.cs`

## 决策

- Phase 74 不重构 graph parser 架构。
- Phase 74 不扩大 P73 恢复窗口。
- Phase 74 只修正 PinReference 与 owning pin body 的主路径读取边界。
- Phase 73 trace/report 保留为验证信号。
