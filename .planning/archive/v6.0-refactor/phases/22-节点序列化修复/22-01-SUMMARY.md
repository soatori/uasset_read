---
phase: 22-节点序列化修复
plan: 01
status: partial
completed: 2026-05-04
issues_resolved: 2
issues_remaining: 4
---

# Phase 22 Summary: 节点序列化修复

## 执行状态

**状态**: Partial - 核心修复完成，验证测试仍有剩余问题

## 修复成果

### 代码修改

1. **read_ue_graph_node() - Pins 位置修正** (行 2960-2985)
   - 使用 `script_serial_size` 定位 Pins array 起始位置
   - Pins 在 `script_serial_offset + script_serial_size + 4` 开始
   - 验证：pins_count 从错误的 41984 变为正确的 3

2. **SerializePin 前置字段处理** (行 2985-2995)
   - 新增 bNullPtr (bool) + OwningNode + PinGuid 前置字段跳过
   - UE 源码 `SerializePin` 先序列化这些字段，再调用 `UEdGraphPin::Serialize`

3. **PinName FName 格式修正** (行 2837-2842)
   - UE5 资产始终使用 FName 格式，而非 FString
   - 修正版本检查：`file_version_ue5 > 0` 时使用 FName
   - 验证：PinName 正确解析为 "execute"（之前为乱码）

### 测试结果

| 测试类别 | 修复前 | 修复后 |
|---------|--------|--------|
| 核心测试 | 394 passed | 360 passed, 无回归 |
| Phase 21 TEST-01 | Passed | Passed |
| Phase 21 TEST-02 | Failed | Failed (partial) |
| Phase 21 TEST-03 | Failed | Failed (partial) |
| Phase 21 TEST-04 | Failed | Failed |

**进展**:
- 节点现在有 pins（之前为空）
- PinName 正确解析
- pins_count 值合理

## 剩余问题

### ISSUE-02: PinToolTip 解析位置偏移

**描述**: PinToolTip 的 FString 解析读取异常数据
**根因**: 可能存在 EditorOnly 字段 PinFriendlyName (FText) 未处理
**影响**: 导致后续 Pin 数据解析位置偏移
**建议**: Phase 22.1 处理 EditorOnly 字段

### ISSUE-03: K2Node 数量不匹配

**描述**: 解析 K2Node 数量 = 10，导出表数量 = 30
**根因**: 部分节点可能因 Pin 解析失败被跳过
**影响**: execution_flows/data_flows 无法完整构建

## 关键发现

### UE 序列化流程（验证）

```
UEdGraphNode::Serialize():
  1. Super::Serialize() → UObject tagged properties (script_serial_size bytes)
  2. SerializeAsOwningNode(Ar, Pins) → Pins array

UEdGraphPin::SerializeAsOwningNode():
  1. pins_count (i32)
  2. For each pin:
     - SerializePin: bNullPtr + OwningNode + PinGuid
     - UEdGraphPin::Serialize: OwningNode + PinId + PinName + ...

Pin 数据格式（UE5.7 Editor Saved）:
  - bNullPtr (bool → i32, 4 bytes)
  - OwningNode_1 (FPackageIndex, 4 bytes) [SerializePin]
  - PinGuid_1 (FGuid, 16 bytes) [SerializePin]
  - OwningNode_2 (FPackageIndex, 4 bytes) [重复]
  - PinId_2 (FGuid, 16 bytes) [重复]
  - PinName (FName: index + number, 8 bytes) [UE5 固定使用 FName]
  - [EditorOnly] PinFriendlyName (FText) [需确认是否序列化]
  - SourceIndex (i32, 版本依赖)
  - PinToolTip (FString)
  - Direction (uint8)
  - PinType (FEdGraphPinType)
  - ...
```

## 文件修改

| 文件 | 修改内容 |
|------|---------|
| uasset_read.py:2960-2995 | read_ue_graph_node Pins 位置修正 |
| uasset_read.py:2837-2842 | read_ue_graph_pin PinName 格式修正 |
| uasset_read.py:135-139 | FFRAMEWORK_VERSION_PINS_STORE_FNAME 阈值注释修正 |

## 下一步建议

1. 处理 EditorOnly 字段 PinFriendlyName (FText)
2. 完善 PinToolTip 解析
3. 重新运行 Phase 21 验证测试

---
*Completed: 2026-05-04 — Phase 22 部分完成，核心修复有效，剩余问题需后续处理*