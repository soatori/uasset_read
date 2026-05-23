---
phase: 72-E
plan: 01
wave: 1
title: "EventGraph 节点解析修复 — 5 个 Issue 修复"
objective: "修复 BP_FirstPersonCharacter.uasset EventGraph 解析覆盖率从 ~56% 提升至 >90%，解决 5 个已识别的根因问题"
gap_closure: false
files_modified:
  - src/uasset_read/archive.py
  - src/uasset_read/serializers/graph.py
  - src/uasset_read/blueprint/variable_extractor.py
  - src/uasset_read/blueprint/component_extractor.py
  - tests/test_graph_parsing.py
---

# Plan 72E-01: EventGraph 节点解析修复

## Objective

修复 BP_FirstPersonCharacter.uasset EventGraph 解析覆盖率从 ~56% 提升至 >90%，解决 5 个已识别的根因问题。

## Tasks

### Task 1: 修复 `read_name()` sentinel 值 (Issue 2)
**文件:** `src/uasset_read/archive.py` — 保持 `"None"` 返回值（PropertyTag 依赖），添加 debug logging。

### Task 2: 增强节点收集 fallback (Issue 1)
**文件:** `src/uasset_read/serializers/graph.py` L1017-1055 — `nodes_count == 0 OR len(nodes) == 0` 时执行 fallback。

### Task 3: K2Node_Event 解析诊断与修复 (Issue 3)
**文件:** `src/uasset_read/serializers/graph.py` L794-986 — 添加边界保护，诊断 script_serial_size 问题。

### Task 4: 组件提取验证 (Issue 4)
**文件:** `src/uasset_read/blueprint/component_extractor.py` — 添加 debug logging。

### Task 5: Blueprint.functions 从 EventGraph 提取 (Issue 5)
**文件:** `src/uasset_read/blueprint/variable_extractor.py` — 从 K2Node_FunctionEntry 提取。

### Task 6: 编写测试验证修复
**文件:** `tests/test_graph_parsing.py` — 5 个测试用例对应验收标准。
