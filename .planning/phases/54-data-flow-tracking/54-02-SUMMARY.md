---
phase: 54-data-flow-tracking
plan: 02
subsystem: data_flow_core
tags: [data-flow, knot-chain, boundary-detection, backward-traversal]
dependencies:
  requires: [54-01]
  provides: [DATA_BOUNDARY_NODES, is_boundary_node, _resolve_knot_chain]
  affects: [src/uasset_read/constants.py, src/uasset_read/graph/flow_builder.py]
tech_stack:
  added: [frozenset constant, boundary detection, knot chain traversal]
  patterns: [backward traversal, visited set for cycle detection]
key_files:
  created: []
  modified:
    - src/uasset_read/constants.py (+9 lines, DATA_BOUNDARY_NODES)
    - src/uasset_read/graph/flow_builder.py (+76 lines, 2 functions)
    - tests/fixtures/data_flow_fixture.py (+5 lines, bidirectional connections)
    - tests/test_output_formatting.py (+114 lines, 7 new tests)
decisions:
  - D-54-02-01: Use InputPin for backward Knot traversal (not OutputPin)
  - D-54-02-02: Target pin is self alias (both stop tracking)
  - D-54-02-03: VariableGet is NOT a boundary (continue tracking)
metrics:
  duration: 180s
  completed: "2026-05-17T15:12:50Z"
  test_count: 7
  file_count: 4
---

# Phase 54 Plan 02: 核心追踪函数 Summary

## 一句话总结

实现了数据流核心追踪函数：DATA_BOUNDARY_NODES 常量、is_boundary_node 边界检测、_resolve_knot_chain Knot 链穿透，为数据源追踪提供基础能力。

## 完成的工作

### Task 1: 实现 DATA_BOUNDARY_NODES 常量

**文件：** `src/uasset_read/constants.py` (+9 lines)

添加了 `DATA_BOUNDARY_NODES` frozenset 常量：
- `K2Node_FunctionEntry`: 函数参数输出作为数据流起点
- `K2Node_VariableSet`: 本地变量定义（边界）

**设计决策：**
- VariableGet 不在边界集合中（应继续追踪）
- Self 引用通过 pin_name 检测，不在此集合中

### Task 2: 实现 is_boundary_node 函数

**文件：** `src/uasset_read/graph/flow_builder.py` (+18 lines)

实现了边界检测函数：
- 检查 `node.class_name in DATA_BOUNDARY_NODES`
- 检查 `pin_name.lower() == "self"` 或 `"target"`
- 返回 True（停止追踪）或 False（继续追踪）

**设计决策：**
- Target 是 self 的别名（UE 中常用的命名）
- Knot 不是边界（需要穿透）

### Task 3: 实现 _resolve_knot_chain 函数

**文件：** `src/uasset_read/graph/flow_builder.py` (+58 lines)

实现了 Knot 链穿透函数：
- 使用 `visited: Set[str]` 防止循环
- 使用 InputPin 进行反向遍历（找到数据来源）
- 最大深度 20 防止恶意循环

**设计决策：**
- **关键修正：** 使用 InputPin 进行反向遍历，而非 OutputPin
- InputPin 的 linked_to_raw 指向数据来源
- OutputPin 的 linked_to_raw 指向数据去向

### Task 4: 启用 Wave 0 测试并验证核心函数

**文件：** `tests/test_output_formatting.py` (+114 lines)

添加了 7 个核心函数单元测试：
1. `test_trace_data_source_knot_chain_direct`: Knot 链穿透测试
2. `test_trace_data_source_function_entry_direct`: FunctionEntry 边界测试
3. `test_is_boundary_node_self_reference`: self/Target 边界测试
4. `test_is_boundary_node_variable_set`: VariableSet 边界测试
5. `test_is_boundary_node_knot`: Knot 不是边界测试
6. `test_resolve_knot_chain_cycle_detection`: 循环检测测试
7. `test_resolve_knot_chain_non_knot_terminal`: 非 Knot 终端测试

**结果：** 7 passed, 4 skipped, 117 deselected

## 提交记录

| Task | Hash | 文件 | 说明 |
|------|------|------|------|
| Task 1 | ef89643 | constants.py | DATA_BOUNDARY_NODES 常量 |
| Task 2 | 8a05af1 | flow_builder.py | is_boundary_node 函数 |
| Task 3 | b868d37 | flow_builder.py | _resolve_knot_chain 函数 |
| Task 4 | 2c2ebcd | 多文件 | 测试 + Bug 修复 |

## Deviations from Plan

### Auto-fixed Issues (Rule 1 - Bug)

**1. [Rule 1 - Bug] Fix _resolve_knot_chain traversal direction**
- **Found during:** Task 4 test execution
- **Issue:** 原实现使用 OutputPin 进行正向遍历，但反向追踪需要使用 InputPin
- **Fix:** 改为使用 InputPin (direction=0) 的 linked_to_raw 进行反向遍历
- **Files modified:** src/uasset_read/graph/flow_builder.py
- **Commit:** 2c2ebcd

**2. [Rule 1 - Bug] Fix is_boundary_node Target detection**
- **Found during:** Task 4 test execution
- **Issue:** test_is_boundary_node_self_reference 测试期望 Target 作为 self 别名
- **Fix:** 添加 `pin_lower == "target"` 检测条件
- **Files modified:** src/uasset_read/graph/flow_builder.py
- **Commit:** 2c2ebcd

**3. [Rule 1 - Bug] Fix data_flow_fixture bidirectional connections**
- **Found during:** Task 4 test execution
- **Issue:** fixture 中多个 pin 的 linked_to_raw 为空，导致测试失败
- **Fix:** 添加双向连接：
  - ScaleValue ← Knot_1 OutputPin
  - knot2_input ← FunctionEntry Left/Right
  - knot1_input ← Knot_2 OutputPin
  - call7346_scale ← Knot_4 OutputPin
- **Files modified:** tests/fixtures/data_flow_fixture.py
- **Commit:** 2c2ebcd

**4. [Rule 1 - Bug] Fix data_flow_fixture K2NodeKnot initialization**
- **Found during:** Task 4 test execution
- **Issue:** `K2NodeKnot()` 缺少必需的 node_guid 参数
- **Fix:** 为所有 4 个 K2NodeKnot 实例添加 node_guid 参数
- **Files modified:** tests/fixtures/data_flow_fixture.py
- **Commit:** 2c2ebcd

**5. [Rule 1 - Bug] Fix test node_guid lookup**
- **Found during:** Task 4 test execution
- **Issue:** 测试使用 `"7445" in n.node_guid` 但实际 GUID 不包含该字符串
- **Fix:** 改为通过 class_name + function_name + GUID 组合查找节点
- **Files modified:** tests/test_output_formatting.py
- **Commit:** 2c2ebcd

## 已知 Stubs

None - 核心函数已完整实现。

## Threat Flags

None - 纯数据结构遍历，无安全风险。

## Self-Check: PASSED

验证项：
- ✅ DATA_BOUNDARY_NODES 常量存在（2 items）
- ✅ is_boundary_node 函数可导入
- ✅ _resolve_knot_chain 函数可导入
- ✅ 7 个测试通过
- ✅ Commit ef89643 存在
- ✅ Commit 8a05af1 存在
- ✅ Commit b868d37 存在
- ✅ Commit 2c2ebcd 存在

## 下一步

**Wave 2（Plan 03）：**
1. 实现 `_trace_data_source` 函数 — 完整数据源追踪
2. 实现 `_annotate_data_providers` 函数 — 正向标注
3. 集成到 `build_execution_flows` 输出
4. 取消剩余 Wave 0 测试 skip 并验证

**验收标准：**
- 6 个 Wave 0 测试全部取消 skip 并通过
- FunctionEntry 参数正确标注
- Pure 函数 ReturnValue 作为数据源
- self pin 作为边界
- SubPin 仅展开第一级
- data_providers 双向标注完成

---

*Created: 2026-05-17T15:12:50Z*
*Duration: 180s*
*Commits: ef89643, 8a05af1, b868d37, 2c2ebcd*