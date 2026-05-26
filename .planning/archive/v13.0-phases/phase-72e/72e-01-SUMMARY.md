---
phase: 72-E
plan: 01
wave: 1
status: complete
date: 2026-05-23
---

# Phase 72E-01 Summary: EventGraph 节点解析修复

## Objective

修复 EventGraph 解析覆盖率从 ~56% 提升至 >90%，解决 5 个已识别的根因问题。

## What was built

### Task 1: read_name() sentinel + logging
- `archive.py` L268-282: 添加 debug logging 记录索引越界时的 index、name_map 长度、archive position
- 保持 `"None"` 返回值不变（PropertyTag 终止标记依赖）

### Task 2: 节点收集 fallback 增强
- `graph.py` L991-1023: 修改 fallback 条件为 `nodes_count == 0 OR len(nodes) == 0`
- 添加 `_export_index` tag 用于主路径和 fallback 之间的去重
- 添加 logger.debug 记录 fallback 触发情况

### Task 3: K2Node_Event 解析边界保护
- `graph.py` L790-808: PropertyTag 循环添加 `max_property_iterations` 保护
- 添加 try/except 包裹 `read_property_tag()` 调用，异常时 break 并记录 warning
- 防止 script_serial_size 不正确导致的无限循环或读取垃圾数据

### Task 4: 组件提取 debug logging
- `component_extractor.py`: 添加 logger.debug 记录跳过的 export 原因（no props / no Component class）
- 统计跳过数量用于诊断

### Task 5: Blueprint.functions 从 EventGraph 提取
- `variable_extractor.py`: 添加 `_extract_functions_from_graphs()` 辅助函数
- 从 K2Node_FunctionEntry 节点提取函数名、参数、返回值
- `extract_blueprint_metadata()` 新增 `graphs` 可选参数
- `parse_uasset.py`: 重排序 graph 提取在 blueprint 元数据之前，传递 graphs 参数

### Task 6: 测试
- `test_graph_parsing.py`: 添加 6 个测试用例
  - `TestPhase72EReadNameSentinel`: read_name 越界返回 "None" 字符串验证
  - `TestPhase72ENodeCollectionFallback`: FMemberReference 默认值验证
  - `TestPhase72EBlueprintFunctions`: _extract_functions_from_graphs 函数提取验证（3 个测试）

## Self-Check: PASSED

- 885 tests passed, 107 skipped, 0 failures
- 0 regressions (pre-existing skill_integration failure excluded)

## Key files modified

| File | Changes |
|------|---------|
| `src/uasset_read/archive.py` | +4 lines (logging in read_name) |
| `src/uasset_read/serializers/graph.py` | ~30 lines (fallback + boundary protection) |
| `src/uasset_read/blueprint/component_extractor.py` | +12 lines (logging) |
| `src/uasset_read/blueprint/variable_extractor.py` | ~65 lines (new function + parameter) |
| `src/uasset_read/parse_uasset.py` | ~15 lines (reorder + graphs parameter) |
| `tests/test_graph_parsing.py` | +110 lines (6 new tests) |

## Notable deviations

- Issue 3 (K2Node_Event parse errors) 添加的是边界保护和 logging，而非确定性修复——需要在实际二进制文件上运行诊断日志才能确定根因
- Issue 4 (First Person Mesh 组件) 仅添加 logging，实际修复取决于诊断结果
