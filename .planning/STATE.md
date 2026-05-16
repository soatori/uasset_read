---
gsd_state_version: 1.0
milestone: v8.0
milestone_name: BP-to-CPP 翻译能力
status: complete
last_updated: "2026-05-16T15:00:00.000Z"
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 4
  completed_plans: 4
  percent: 100
---

# v8.0 — BP-to-CPP 翻译能力

## 问题: v7.0 解析结果无法支撑 BP→C++ 翻译

对比 `BP_FirstPersonCharacter.uasset` 解析 JSON 与等价 C++ 实现
(`FirstPersonCCharacter.cpp/h`)，发现 6 个结构性 gap：

| 当前 | 目标 |
|------|------|
| ~~linked_to_raw 全空~~ | ✅ Phase 47 已修复 |
| ~~无组件数值属性~~ | ✅ Phase 48 已实现 |
| ~~CallFunction pins 不完整~~ | ✅ Phase 49 已实现 |
| ~~EnhancedInput 触发事件不可见~~ | ✅ Phase 50 已实现 |

## Phase 分解

| Phase | 名称 | 状态 |
|-------|------|------|
| 47 | Pin LinkedTo 修复 | ✅ 完成 |
| 48 | 组件属性递归解析 | ✅ 完成 |
| 49 | 函数调用引脚解析 | ✅ 完成 |
| 50 | EnhancedInput 语义增强 | ✅ 完成 |
| 51 | 二进制输出清理 | 🔴 未开始 |

## Phase 49: 函数调用引脚解析 ✅

**实现:** `_extract_call_function_parameters()` — 从 CallFunction 节点 pins 提取参数，
过滤 exec pins，分离输入/输出参数为结构化数组。`format_node_dict()` 添加 `parameters` 字段。
`_trace_execution_from_event()` 添加简化 `params` 数组到执行流。

**变更文件:**
- `src/uasset_read/formatters/json_formatter.py` — 新增 `_extract_call_function_parameters()`
- `src/uasset_read/graph/flow_builder.py` — `format_node_dict()` + `_trace_execution_from_event()` 扩展
- `src/uasset_read/models/core.py` — 同步 FEdGraphPinType 字段

**测试:** 7/7 passed，0 new regressions。

## 验证标准 — JSON 可翻译性

- ~~Phase 47: connections > 0, execution_flows[].nodes 非空~~ ✅ 已完成
- ~~Phase 48: components 数组包含数值属性（位置/旋转/缩放/标志）~~ ✅ 已完成
- ~~Phase 49: CallFunction 节点输出 parameters 数组（参数名+类型）~~ ✅ 已完成
- ~~Phase 50: trigger_events 非空，与 C++ SubscribeToAction 对应~~ ✅ 已完成

JSON 输出已达到"人工可对照 C++ 头文件/构造函数/函数体逐行翻译"的程度。

*Updated: 2026-05-16*
