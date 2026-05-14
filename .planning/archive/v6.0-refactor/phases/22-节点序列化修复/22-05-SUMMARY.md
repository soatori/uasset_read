---
phase: 22-节点序列化修复
plan: 05
status: partial
completed: 2026-05-05
issues_resolved: 0
issues_remaining: 4
---

# Phase 22 Plan 05 Summary: 动态扫描定位 pins_offset

## 执行状态

**状态**: Partial — 核心修复已实现，但 Pin 解析位置问题仍未解决

## 关键发现

### 发现 1: 动态扫描方案有效

通过二进制分析确认：
- 正确的 pins_offset 位于 `scan_start + 4` (pos=4)
- Pattern: pins_count=4, bNullPtr=0, OwningNode=32
- 动态扫描能准确定位 pins 数组起始位置 ✓

### 发现 2: FText history_type=255 固定 pattern

实测数据显示所有 UE5 资产中存在固定的 17 bytes FText pattern：
```
00000000ff00000000ffffffff00000000
```
- flags=0, history_type=255
- 后续 12 bytes 固定数据
- 这不是标准 FText 格式，需要特殊处理 ✓

### 发现 3: PinType 读取位置错误

从手动验证：
- Direction 在 offset 73 ✓
- PinCategory 在 offset 74，idx=148 -> "exec" ✓
- 但代码执行时 PinCategory=None ✗

**根因**: read_ed_graph_pin_type 的 bool 读取使用了 `read_bool()` (4 bytes)，但 UE5 中某些 bool 字段使用 `read_u8()` (1 byte)

### 发现 4: MemberReference 版本检查问题

- `has_member_reference = True` (基于 file_version_ue4 >= 500)
- MemberReference 字段（28 bytes）被读取
- 但版本检查和 bool 格式不匹配导致位置错乱

## 代码修改

### 已实现修改

| 文件 | 修改内容 |
|------|---------|
| uasset_read.py:3067-3132 | 动态扫描替代 heuristic_delta |
| uasset_read.py:2857-2869 | history_type=255 特殊处理（跳过 12 bytes）|

### 未实现（需要后续 Phase）

| 问题 | 建议 |
|------|------|
| bool 序列化格式 | UE5 bool 使用 uint8 (1 byte)，需要修改 `read_bool()` 或创建 `read_u8_bool()` |
| MemberReference 版本检查 | 需要研究 UE 源码中 VER_UE4_MEMBERREFERENCE_IN_PINTYPE 的实际值 |
| read_ed_graph_pin_type delta | 需要系统性重构版本检查逻辑 |

## 测试结果

| 测试 | 修复前 | 修复后 | 说明 |
|------|--------|--------|------|
| TEST-01: K2Node 数量 | PASSED | PASSED | 保持不变 |
| TEST-02: execution_flows | FAILED | FAILED | Pin 解析问题未解决 |
| TEST-03: data_flows | FAILED | FAILED | Pin 解析问题未解决 |
| TEST-04: function_reference | PASSED | FAILED | 位置错乱导致新问题 |

## 下一步建议

### 建议 1: 创建专门的 UE5 bool 读取方法

```python
def read_bool_ue5(self) -> bool:
    """UE5 bool 序列化为 uint8 (1 byte)"""
    return self.read_u8() != 0
```

### 建议 2: 研究 UE 源码中的版本常量

需要确定：
- VER_UE4_MEMBERREFERENCE_IN_PINTYPE 的实际版本号
- VER_UE4_SERIALIZE_PINTYPE_CONST 的实际版本号
- UE5 中这些版本是否启用

### 建议 3: 创建新 Phase 22-06

问题需要系统性重构：
- Phase 22-06: UE5 bool 序列化格式修复
- Phase 22-07: read_ed_graph_pin_type 版本检查重构

## 手动验证参考

正确的 Pin 数据结构（offset 从 pins_start 计算）：

| Offset | 字段 | 值 |
|--------|------|-----|
| 0 | pins_count | 4 |
| 4-27 | SerializePin (Pin 1) | bNull=0, Owning=32, Guid |
| 28-47 | UEdGraphPin Owning+Guid | Owning=32, Guid |
| 48-55 | PinName (FName) | idx=149 -> "execute" |
| 56-72 | FText (17 bytes) | 固定 pattern |
| 73 | Direction | 0 |
| 74-126 | PinType | PinCategory=148 -> "exec" ✓ |
| 127-138 | Defaults | DefaultValue="", AutoDef="", DefObj=0 |
| 139-146 | LinkedTo/SubPins | counts=0 |
| 147-174 | ParentPin/RefPass | bNull=0/非0 |

---
*Completed: 2026-05-05 — Phase 22-05 partial progress，核心修复已实现，需要后续 Phase 解决 bool 序列化格式问题*