---
status: investigating
trigger: Pin解析器无法定位pins_offset — MemberReference字段版本条件问题
created: "2026-05-11T15:00:00.000Z"
updated: "2026-05-11T18:30:00.000Z"
---

# Debug Session: pin-parsing-pins-offset

## Symptoms

**Expected:** 4个测试通过 (test_jump_started_flow, test_jump_completed_flow, test_actionvalue_x_to_right, test_execution_flows_contains_function_name)

**Actual:** 4个测试失败 — 节点未找到/数据流缺失/function_name为空

**Error Messages:**
- test_jump_started_flow: Jump节点未找到
- test_jump_completed_flow: StopJumping节点未找到
- test_actionvalue_x_to_right: Move数据流缺失
- test_execution_flows_contains_function_name: function_name为空

**Timeline:** 从9失败降到4失败 (stash合并修复了5个)，剩4个pin解析问题

**Reproduction:**
```bash
python -m pytest tests/test_phase21_verification.py::test_jump_started_flow tests/test_phase21_verification.py::test_jump_completed_flow tests/test_phase21_verification.py::test_actionvalue_x_to_right tests/test_skill_integration.py::test_execution_flows_contains_function_name -v
```

## Current Focus

hypothesis: "CustomVersion GUID 字节序错误导致版本检查失败，导致 FEdGraphPinType 解析使用错误格式"
test: "验证 GUID 格式修复后的版本值是否正确获取"
expecting: "framework_version=37, release_version=44, mainstream_version=121"
next_action: "分析 K2Node_CallFunction 序列化顺序，确定 Pins 与 FunctionReference 字段的位置关系"

reasoning_checkpoint: |
  已修复：
  1. GUID 字节序：从 `CFFC743F-43B04480-...` 改为 `3F74FCCF8044B043DF14919373201D17`（小端序）
  2. 版本获取：现在正确返回 framework_version=37, release_version=44, mainstream_version=121
  3. FName 序列化：确认 FName = 8 bytes（index + number），而非 4 bytes
  4. FEdGraphPinType：现在正确解析 65 bytes（使用 CustomVersion 版本检查）
  
  新发现：
  1. FSimpleMemberReference 在 PinType 中序列化为 28 bytes（Parent 4 + Name 8 + Guid 16）
  2. bool 在 UE 中序列化为 UBOOL（4 bytes），而非 1 byte
  3. EditorOnly 字段（PersistentGuid, BitField）在未 cooked 资产中存在
  
  待解决：
  - Pin #0 解析完成后，offset 在 0x16d81
  - 但 0x16d81 处的数据不是下一个 pin 的 bNullPtr
  - 数据看起来像是 PersistentGuid 的重复内容
  - 可能：K2Node_CallFunction 的 FunctionReference 在 Pins 之后序列化

## Evidence

- timestamp: "2026-05-11T14:30:00"
  observation: "测试从9失败降到4失败，确认pin解析是剩余根因"
  source: "pytest output"

- timestamp: "2026-05-11T14:35:00"
  observation: "MemberReference字段在当前代码无条件读取"
  source: "uasset_read.py:read_ed_graph_pin_type"

- timestamp: "2026-05-11T15:30:00"
  observation: "资产版本：file_version_ue4=522, file_version_ue5=1017, 不是 -9！"
  source: "Python 直接读取资产头"

- timestamp: "2026-05-11T16:00:00"
  observation: "CustomVersion GUID 字节序错误：代码用大端序，文件用小端序"
  source: "对比 DevObjectVersion.cpp GUID 定义与资产中存储的 GUID"

- timestamp: "2026-05-11T16:30:00"
  observation: "GUID 修复后版本正确获取：framework=37, release=44, mainstream=121"
  source: "解析测试"

- timestamp: "2026-05-11T17:00:00"
  observation: "FName 序列化 = 8 bytes（index uint32 + number uint32）"
  source: "调试输出：PinCategory/SubCategory 16 bytes"

- timestamp: "2026-05-11T17:30:00"
  observation: "bool 序列化 = UBOOL（uint32, 4 bytes）"
  source: "调试输出：bIsReference/WeakPointer 8 bytes，bIsConst 4 bytes"

- timestamp: "2026-05-11T18:00:00"
  observation: "Pin #0 解析结束在 0x16d81，但 0x16d81 处不是下一个 pin 的 bNullPtr"
  source: "调试输出：bNullPtr=-212730201（无效值）"

- timestamp: "2026-05-11T18:15:00"
  observation: "0x16d81 处的数据是 a7fe51f308fb19c3，像是 FGuid 的前半部分"
  source: "直接读取资产文件数据"

## Eliminated

- hypothesis: "测试本身有bug"
  reason: "已修复5个测试，剩4个均为pin解析相关，模式一致"

- hypothesis: "FileVersionUE4 = -9 导致版本检查失败"
  reason: "实际版本是 522（UE4 最新版本）和 1017（UE5）"

- hypothesis: "MemberReference 字段版本条件问题"
  reason: "GUID 修复后版本检查正确工作，MemberReference 正确读取"

## Resolution

root_cause: CustomVersion GUID 字节序错误 + K2Node_CallFunction 序列化顺序未正确处理
fix: 部分修复：GUID 字节序已修复，版本检查正确。待解决：节点类型特定序列化顺序
verification: 运行测试，当前仍4失败
files_changed:
  - uasset_read.py (GUID 字节序修复)
  - uasset_read.py (read_ed_graph_pin_type 函数重写)
## Additional Evidence (Session Continuation)

- timestamp: "2026-05-11T19:00:00"
  observation: "pins_offset 计算公式修复：从扫描策略改为固定公式 `script_serial_offset + script_serial_size`"
  source: "UE 源码分析 + 实际数据验证"
  result: "pins_count 从 0 变为正确值（如 4）"

- timestamp: "2026-05-11T19:10:00"
  observation: "测试结果：只剩1个测试失败（test_jump_started_flow），其他275个测试通过"
  source: "pytest output"

- timestamp: "2026-05-11T19:15:00"
  observation: "剩余问题：FunctionReference 读取位置错误。当前代码在 Pins 之后调用 read_k2node_call_function，但 FunctionReference 应该在 script_serial 中（Pins 之前）"
  source: "UE 序列化顺序分析"

## Resolution Update

root_cause: 序列化顺序理解错误导致 pins_offset 计算错误 + FunctionReference 读取位置错误
fix_part1: 已修复 pins_offset 计算公式（从扫描改为固定公式 `script_serial_offset + script_serial_size`）
fix_part2: 待修复 FunctionReference 读取位置（需要在 script_serial 中读取，而不是在 Pins 之后）
verification: 运行测试，当前1个失败，275个通过
files_changed:
  - uasset_read.py (L3999-4020: pins_offset 计算公式修复)

## Next Action

需要进一步修复：
1. 在 read_ue_graph_node 开始时，从 script_serial 中查找并读取 FunctionReference
2. 或者在 read_ue_graph_node 中正确处理序列化顺序：先读取 UPROPERTY 字段（从 script_serial），再读取 Pins

建议：实现 tagged property serialization 解析，或者使用反向查找策略在 script_serial 中定位 FunctionReference。
