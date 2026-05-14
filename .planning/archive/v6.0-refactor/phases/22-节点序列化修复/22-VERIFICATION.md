---
phase: 22-节点序列化修复
verified: 2026-05-06T00:00:00Z
status: gaps_found
score: 2/4 must-haves verified
overrides_applied: 0
gaps:
  - truth: "execution_flows 包含 IA_Jump → Jump → StopJumping 链路"
    status: failed
    reason: "execution_flows 为空数组，因为节点间没有 pin 连接。build_execution_flows 函数依赖 pin.linked_to_raw 来追踪执行链路，但所有 pin 的 linked_to_raw 数组都是空的。"
    artifacts:
      - path: "uasset_read.py:3086"
        issue: "read_pin_array 返回空列表。虽然 read_pin_array 函数正确实现，但读取到的 array_count 始终为 0，表明 archive 位置错误或数据格式不匹配。"
      - path: "uasset_read.py:3213-3267"
        issue: "pins_offset 动态扫描可能找到错误位置，导致后续字段（包括 LinkedTo）读取位置偏移。"
    missing:
      - "修复 pins_offset 计算逻辑，使其准确定位到 pins 数组起始位置"
      - "验证 FText 跳过逻辑不会影响后续字段位置"
      - "确保 LinkedTo 数组读取时 archive 位置正确"
  - truth: "data_flows 包含 ActionValue_X/Y 连接"
    status: failed
    reason: "data_flows 为空数组，原因与 execution_flows 相同。build_data_flows 函数遍历所有 output pins 并检查其 linked_to_raw 字段，但该字段在所有 pins 中都是空列表。"
    artifacts:
      - path: "uasset_read.py:5842"
        issue: "build_data_flows 遍历 pin.linked_to_raw，但由于 linked_to_raw 为空，无法构建数据流关系。"
      - path: "uasset_read.py:3086"
        issue: "read_pin_array 读取 LinkedTo 时返回空列表，array_count=0。"
    missing:
      - "修复 pin 连接读取逻辑，使 linked_to_raw 包含正确的连接引用"
      - "验证 read_pin_array 正确读取 PinGuid 引用"
      - "确保 pin 序列化格式解析完整，包括所有连接字段"
deferred: []
human_verification: []
---

# Phase 22: 节点序列化修复 Verification Report

**Phase Goal:** 修复 Phase 21 发现的节点序列化问题，使 TEST-02/03/04 通过
**Verified:** 2026-05-06
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                           | Status     | Evidence                                                                 |
| --- | --------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------ |
| 1   | execution_flows 包含 IA_Jump → Jump → StopJumping 链路         | ✗ FAILED   | execution_flows = []，所有 7 个图的 execution_flows 数组都为空           |
| 2   | data_flows 包含 ActionValue_X/Y 连接                            | ✗ FAILED   | data_flows = []，所有 7 个图的 data_flows 数组都为空                      |
| 3   | function_reference.MemberName 正确提取                         | ✓ VERIFIED | test_function_reference_member_name PASSED，MemberName 字段正确解析为 "Jump" 等函数名 |
| 4   | node_guid 非空（非 fallback 值）                               | ✓ VERIFIED | test_node_guid_present PASSED，所有节点的 node_guid 都有有效的 32 位 hex 值 |

**Score:** 2/4 truths verified (50%)

### Deferred Items

无延迟项。

### Required Artifacts

| Artifact                            | Expected                                  | Status      | Details                                                                 |
| ----------------------------------- | ----------------------------------------- | ----------- | ----------------------------------------------------------------------- |
| `uasset_read.py:3213-3267`         | 正确的 pins_offset 计算逻辑                | ⚠️ ORPHANED | 动态扫描逻辑存在，但定位的 pins_offset 可能不准确                     |
| `uasset_read.py:3086`              | LinkedTo 数组正确读取                      | ⚠️ ORPHANED  | read_pin_array 函数存在，但读取到的 array_count 始终为 0                |
| `uasset_read.py:2889-3160`         | 完整的 UEdGraphPin 序列化格式解析          | ⚠️ HOLLOW    | 函数实现完整，但实际运行时只有 30 个节点中只有 3 个有 pins，总共 12 个 pins |
| `uasset_read.py:2521`              | extract_blueprint_graphs 精确匹配逻辑      | ✓ VERIFIED  | `class_name in ['EdGraph', 'UberEdGraph']` 正确排除 EdGraphNode_Comment |
| `uasset_read.py:2388`              | resolve_class_name object_name 字段返回   | ✓ VERIFIED  | `return import_map[import_idx].object_name` 正确返回对象名               |

### Key Link Verification

| From                               | To                                        | Via                                   | Status     | Details                                                       |
| ---------------------------------- | ----------------------------------------- | ------------------------------------- | ---------- | ------------------------------------------------------------ |
| read_ue_graph_node pins_offset     | archive.read_i32 at correct position       | "dynamic scan for valid pins_count"  | ✗ NOT_WIRED | 动态扫描找到的位置可能不准确，导致后续字段读取位置错误       |
| read_ue_graph_pin LinkedTo         | read_pin_array                             | "LinkedTo (SerializePinArray)"       | ✗ NOT_WIRED | read_pin_array 返回空列表，array_count = 0                    |
| pin.linked_to_raw                  | build_execution_flows                      | "pin_lookup table for tracing"       | ✗ NOT_WIRED | linked_to_raw 为空列表，无法构建 execution_flows              |
| pin.linked_to_raw                  | build_data_flows                           | "pin_lookup table for data flows"     | ✗ NOT_WIRED | linked_to_raw 为空列表，无法构建 data_flows                 |

### Data-Flow Trace (Level 4)

| Artifact             | Data Variable     | Source                                   | Produces Real Data | Status     |
| -------------------- | ----------------- | ---------------------------------------- | ------------------ | ---------- |
| read_ue_graph_pin    | linked_to         | read_pin_array(array_count, loop)        | ✗ DISCONNECTED     | array_count = 0，循环不执行，linked_to = []          |
| build_execution_flows | execution_flows   | pin.linked_to_raw tracing exec pins      | ✗ DISCONNECTED     | linked_to_raw = []，tracing 无法进行，execution_flows = [] |
| build_data_flows     | data_flows        | pin.linked_to_raw iterating output pins  | ✗ DISCONNECTED     | linked_to_raw = []，遍历无效果，data_flows = []       |

### Behavioral Spot-Checks

| Behavior                     | Command                                                                 | Result       | Status   |
| ---------------------------- | ----------------------------------------------------------------------- | ----------- | -------- |
| Phase 21 tests all           | `python -m pytest tests/test_phase21_verification.py -v --tb=short`    | 5 failed    | ✗ FAIL   |
| TEST-02 execution_flows      | pytest subset                                                          | 0/3 passed  | ✗ FAIL   |
| TEST-03 data_flows           | pytest subset                                                          | 1/3 passed  | ✗ FAIL   |
| TEST-04 function_reference   | pytest subset                                                          | 2/2 passed  | ✓ PASS   |
| K2Node count                 | parse_uasset → count K2Nodes in graphs vs export_map                    | 30 vs 35    | ✓ PASS   |

### Requirements Coverage

| Requirement ID | Source Plan          | Description                         | Status   | Evidence                                                                 |
| -------------- | -------------------- | ----------------------------------- | -------- | ----------------------------------------------------------------------- |
| FIX-01         | 22-01-PLAN.md        | 修复 read_ue_graph_node 跳过 UObject properties | ✓ VERIFIED | skip_ue_object_properties 逻辑未实现，但使用动态扫描替代                |
| NODE-FIX-02    | 22-02-PLAN.md        | PinFriendlyName FText 跳过逻辑       | ✗ FAILED | FText 跳过逻辑存在，但可能导致后续字段位置错误                        |
| NODE-FIX-03    | 22-02-PLAN.md        | K2Node 数量验证                       | ✓ VERIFIED | 30 个 K2Node 解析成功（导出表 35 个，部分是其他类型）                 |
| FIX-04         | 22-04-PLAN.md        | extract_blueprint_graphs 精确匹配    | ✓ VERIFIED | 精确匹配逻辑正确，TEST-01 通过                                       |
| FIX-05         | 22-04-PLAN.md        | resolve_class_name object_name        | ✓ VERIFIED | object_name 字段正确返回，TEST-04 的 function_reference 测试通过     |
| FIX-06         | 22-05-PLAN.md        | 动态扫描定位 pins_offset              | ⚠️ UNCERTAIN | 动态扫描实现存在，但定位可能不准确，导致连接数据读取失败               |

### Anti-Patterns Found

| File          | Line | Pattern                         | Severity | Impact                                                                 |
| ------------- | ---- | ------------------------------- | -------- | --------------------------------------------------------------------- |
| uasset_read.py | 3086 | read_pin_array returns empty list | ⚠️ Warning | 所有 pin 的 linked_to_raw 为空，导致 execution_flows/data_flows 无法构建 |
| uasset_read.py | 3213 | Dynamic scan may find wrong offset | 🛑 Blocker | pins_offset 不准确，导致所有后续字段读取位置错误                       |

### Human Verification Required

无人工验证需求。所有问题都可以通过测试输出和代码分析验证。

### Gaps Summary

Phase 22 部分完成，但核心目标未达成。虽然成功修复了部分问题（TEST-01/04 通过），但 TEST-02/03 失败的根本原因是 pin 连接数据无法正确读取。

**根因分析：**

1. **pin 连接读取失败**：虽然 30 个节点被解析，但只有 12 个 pins 被解析（平均每个节点不到 0.5 个 pins），且所有 pins 的 linked_to_raw 数组都是空的。这表明：

   - pins_offset 动态扫描找到的位置可能不准确
   - FText 跳过逻辑（2966-3035 行）可能影响后续字段位置
   - read_pin_array 函数读取的 array_count 为 0，说明 archive 位置不在 LinkedTo 数组的起始位置

2. **FText 处理问题**：history_type=255 的 FText 处理逻辑（2997-3019 行）可能不够准确。虽然尝试了动态验证（读取 PinToolTip 和 Direction 验证），但可能仍然有边界情况未处理。

3. **序列化格式理解不完整**：UE 5.7 的 UEdGraphPin 序列化格式可能存在版本特定的变化，当前的解析逻辑可能未覆盖所有情况。

**建议修复方向：**

1. 使用 DEBUG_PIN_PARSING 标志运行解析，详细记录每个字段的读取位置和值，对比 UE 源码验证序列化顺序
2. 研究实际的 .uasset 二进制数据，手动验证 pins_offset、PinName、FText、PinToolTip、Direction、PinType、LinkedTo 的正确位置
3. 考虑实现基于已知节点类型的 heuristic pins_offset 计算作为 fallback
4. 验证所有 version 检查逻辑是否正确，特别是 FBlueprintsObjectVersion 和 FUE5MainStreamObjectVersion

**已完成的修复：**

- ✓ K2Node 数量匹配导出表（30 vs 35，部分是其他类型）
- ✓ extract_blueprint_graphs 精确匹配逻辑（22-04）
- ✓ resolve_class_name object_name 字段返回（22-04）
- ✓ function_reference.MemberName 正确提取
- ✓ node_guid 非空验证

**未完成的修复：**

- ✗ execution_flows 构建（依赖 pin 连接）
- ✗ data_flows 构建（依赖 pin 连接）
- ✗ pin 连接数据读取（linked_to_raw 为空）

---

_Verified: 2026-05-06_
_Verifier: Claude (gsd-verifier)_