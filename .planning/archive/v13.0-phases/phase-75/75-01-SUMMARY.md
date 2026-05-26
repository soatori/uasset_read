---
gsd_state_version: 1.0
phase: 75
plan: 01
subsystem: diagnostics
tags: [field-level-diagnostics, pin-trace, BP_FirstPersonCharacter]
dependency_graph:
  requires: [Phase 73 Pin trace infrastructure, Phase 74 PinReference alignment]
  provides: [field-level diagnostic baseline for Phase 75 repair loop]
  affects: [src/uasset_read/graph/pin_trace.py, src/uasset_read/graph/__init__.py]
tech-stack:
  added: [logging.handlers.MemoryHandler, field offset tracing]
  patterns: [read-only diagnostics, trace_mode extension, anomaly reporting]
key-files:
  created:
    - src/uasset_read/graph/pin_trace.py
    - tests/test_phase75_field_level_diagnostics.py
  modified:
    - src/uasset_read/graph/__init__.py
decisions:
  - Extended existing pin_trace.py rather than creating separate diagnostic module (plan Rule 3: reuse trace_mode=True)
  - MemoryHandler for log capture instead of caplog fixture (module-scoped, reusable by future tests)
  - Output to temp/phase75/ with 8 structured files for comprehensive field-level view
metrics:
  duration: ~10m
  completed: "2026-05-26"
---

# Phase 75 Plan 01: 建立字段级诊断基线 总结

**One-liner:** 扩展 pin_trace.py 新增 write_phase75_diagnostic() 只读诊断函数，输出 8 个诊断文件到 temp/phase75/，18 项测试全部通过，确认复现 Phase 75 上下文中的所有异常。

## 实现内容

### 诊断函数 `write_phase75_diagnostic()`

在 `src/uasset_read/graph/pin_trace.py` 新增 Phase 75 诊断入口，复用现有 `trace_mode=True` 机制，扩展为成功/失败都记录。

输出文件（全部在 `temp/phase75/`）：

| 文件 | 内容 |
|------|------|
| `graph_node_counts.json` | 每个 graph 的节点类型计数 |
| `enhanced_input_nodes.json` | 4 个 K2Node_EnhancedInputAction 的 input_action_path、AdvancedPinDisplay、每个 pin 的 name/direction/category/default/link 数量 |
| `event_nodes.json` | 4 个 K2Node_Event 的 EventReference、bOverrideFunction、split pin 状态 |
| `function_entry_nodes.json` | K2Node_FunctionEntry 的 ExtraFlags、bIsEditable、pins |
| `pin_diagnostics.json` | 每个 pin 的 LinkedTo 起点 offset、raw count、resolved count、anomalous fields |
| `linkedto_recovery_summary.txt` | LinkedTo read failed 日志条目汇总、recovery 事件详情 |
| `event_node_fields.json` | 事件节点字段详情，含 recovery reason 关联 |
| `pin_body_offsets.json` | 每个 pin 的完整字段 offset 表（start/end/consumed/value/exception） |

### 测试文件

`tests/test_phase75_field_level_diagnostics.py` 含 18 项断言：
- 9 项文件存在性验证
- 9 项异常复现验证

## 确认的异常

### 异常 Direction 值

| 节点 | Pin | Direction | 类型 |
|------|-----|-----------|------|
| IA_MouseLook | ActionValue_X | 114 | ANOMALY |
| IA_MouseLook | Secondary Thumbstick_256 | 46 | ANOMALY |
| IA_Look | ActionValue_X | 67 | ANOMALY |
| IA_Look | Secondary Thumbstick_256 | 47 | ANOMALY |
| IA_Move | ActionValue_X | 67 | ANOMALY |
| IA_Move | None | 136 | ANOMALY |
| IA_Move | /Game/FirstPerson/... | 97 | ANOMALY |

### LinkedTo read failed 位置

| # | Pos | Bad Count | Node | Pin |
|---|-----|-----------|------|-----|
| 1 | 115013 | 779314540 | K2Node_EnhancedInputAction_1 | ActionValue_X |
| 2 | 115651 | 6912 | - | - |
| 3 | 119045 | 1886220099 | K2Node_EnhancedInputAction_2 | - |
| 4 | 119678 | 6912 | - | - |
| 5 | 123072 | 1886220099 | K2Node_EnhancedInputAction_3 | - |
| 6 | 123630 | 1715769417 | - | - |
| 7 | 130130 | 890210999 | - | - |

### Recovery 统计

- subpins_resync: 7 次（均为 null reference 重同步）
- pin_array_count: 3 次（count=0 后有合法 SubPins count）
- 总计 122 个 pin 被 trace，10 次 recovery 事件

## Decisions Made

1. **复用 pin_trace.py 而非新建模块**：plan 要求"优先复用 trace_mode=True，不要引入第二套解析路径"
2. **MemoryHandler 日志捕获**：module-scoped 可复用，与 caplog fixture 兼容
3. **8 文件分离输出**：每类诊断信息独立文件，便于后续修复时增量对比

## 回归验证

- Phase 73/74 回归：28 tests passed, 9 warnings
- Phase 75 诊断测试：18 tests passed

## 对后续任务的贡献

诊断输出可直接用于 Phase 75-02（golden tests）的失败信息定位和 Phase 75-03+ 的修复验证。
第一个异常 LinkedTo offset 明确指向 `K2Node_EnhancedInputAction_1` 的 `ActionValue_X` pin 在 pos 115013，
raw_count=779314540，这是后续修复循环的起点。
