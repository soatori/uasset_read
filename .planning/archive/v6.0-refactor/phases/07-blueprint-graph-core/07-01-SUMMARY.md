---
phase: 07-blueprint-graph-core
plan: 01
subsystem: blueprint-graph
tags: [data-model, graph-detection, GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04]
dependencies:
  requires: [Phase-6-export-table-fix]
  provides: [UEdGraph-dataclasses, extract_blueprint_graphs]
  affects: [ParseResult]
tech_stack:
  added: []
  patterns: [dataclass, field(default_factory), List-type]
key_files:
  created: []
  modified: [uasset_read.py]
decisions:
  - D-01: LinkedTo 原始数据存储（List[str]），Phase 8 构建映射
  - D-02: 节点类型范围限制（基类字段 + GRAPH-05~09）
  - D-03: 完整解析 Graph→Node→Pin 三层结构
  - D-04: 顶层 graphs 字段，与 blueprint 同级
metrics:
  duration: "5 minutes"
  tasks_completed: 2
  files_modified: 1
  lines_added: 139
  test_status: "85 passed, 23 skipped"
---

# Phase 7 Plan 01: 蓝图图数据结构 + EdGraph 检测 Summary

定义蓝图图三层数据结构（UEdGraph、UEdGraphNode、UEdGraphPin）并实现 EdGraph 导出类型检测，为 Phase 7 图解析奠定数据模型基础。

## Completed Tasks

| Task | Name | Commit | Files Modified |
|------|------|--------|----------------|
| 1 | 定义蓝图图数据类结构 | 99be932 | uasset_read.py |
| 2 | 实现 EdGraph 导出类型检测（GRAPH-01） | 1c83208 | uasset_read.py |

## Task 1: 定义蓝图图数据类结构

新增数据类定义：

1. **UEdGraphPin** - 蓝图引脚完整结构
   - `pin_id`: FGuid hex（16 bytes）
   - `pin_name`: FName 解析结果
   - `direction`: uint8 (0=Input, 1=Output, 2=None)
   - `pin_type`: FEdGraphPinType（复用 Phase 3）
   - `linked_to_raw`: List[str]（D-01 原始数据）
   - `sub_pins`, `parent_pin`, `flags`

2. **UEdGraphNode** - 节点基类
   - `node_guid`: FGuid hex
   - `node_pos_x/y`: 编辑器位置
   - `node_comment`: 注释文本
   - `pins`: List[UEdGraphPin]
   - `class_name`: 类型识别结果
   - `node_data`: Optional[Any]（多态）

3. **UEdGraph** - 图容器
   - `graph_name`: 导出 ObjectName
   - `graph_class`: ClassIndex 解析结果
   - `schema`, `nodes`, `graph_guid`, `b_editable`

4. **FMemberReference** - 成员引用结构
   - 用于 GRAPH-05/06 函数/事件引用
   - `member_parent`, `member_name`, `member_guid`, `b_self_context`

5. **ParseResult 扩展**
   - 新增 `graphs: List[UEdGraph]` 字段（D-04 顶层字段）

## Task 2: EdGraph 导出类型检测

实现 `extract_blueprint_graphs()` 函数：

- **安全检查**: PKG_Cooked 标志检测（T-07-01-02），避免解析已剥离资产
- **类型检测**: 遍历 ExportMap，ClassIndex 包含 "EdGraph" 或 "UberEdGraph" 视为图对象
- **基本信息提取**: 此阶段仅提取 graph_name 和 graph_class，nodes 等推迟到 Wave 2

复用 `get_asset_class()` 函数解析 ClassIndex。

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

本阶段为 Wave 1 实现，以下功能推迟到后续 Wave：

| Stub | File | Line | Reason |
|------|------|------|--------|
| UEdGraph.nodes | uasset_read.py | ~850 | Wave 2 实现 Nodes 数组解析 |
| UEdGraph.schema | uasset_read.py | ~851 | Wave 2 实现 FPackageIndex 解析 |
| UEdGraph.graph_guid | uasset_read.py | ~853 | Wave 2 实现 FGuid 解析 |
| UEdGraphNode.node_data | uasset_read.py | ~834 | Wave 2+ 实现类型特定数据解析 |

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag:cooked-check | uasset_read.py L1627-1631 | PKG_Cooked 检查避免解析已剥离资产（Pitfall 3） |

## Verification

```bash
# 数据类导入验证
python -c "from uasset_read import UEdGraph, UEdGraphNode, UEdGraphPin; print('Import OK')"
# Output: Import OK

# ParseResult graphs 字段验证
python -c "from dataclasses import fields; from uasset_read import ParseResult; f = [f.name for f in fields(ParseResult)]; print('graphs' in f)"
# Output: True

# 函数导入验证
python -c "from uasset_read import extract_blueprint_graphs; print('Import OK')"
# Output: Import OK

# 现有测试无回归
python -m pytest tests/ -v --ignore=tests/test_output_formatting.py -k "not test_json_full_structure"
# Output: 85 passed, 23 skipped
```

## Self-Check: PASSED

- [x] UEdGraph class exists: `grep -c "class UEdGraph:" uasset_read.py` == 1
- [x] UEdGraphNode class exists: `grep -c "class UEdGraphNode:" uasset_read.py` == 1
- [x] UEdGraphPin class exists: `grep -c "class UEdGraphPin:" uasset_read.py` == 1
- [x] ParseResult graphs field exists: verified via dataclasses.fields
- [x] extract_blueprint_graphs function exists: `grep -c "def extract_blueprint_graphs" uasset_read.py` == 1
- [x] Commit 99be932 exists: verified via git log
- [x] Commit 1c83208 exists: verified via git log

---

*Phase: 07-blueprint-graph-core*
*Plan: 01*
*Completed: 2026-05-02*