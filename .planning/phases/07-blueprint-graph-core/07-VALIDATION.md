---
phase: 07
status: planned
created: 2026-05-02
validation_type: nyquist
---

# Phase 7: 蓝图图核心解析 - Validation Strategy

**Purpose:** 映射 Phase 7 需求到测试验证，确保每个 GRAPH 需求有对应测试覆盖。

## Requirements → Tests Mapping

| Req ID | Behavior | Test Name | Test File | Automated |
|--------|----------|-----------|-----------|-----------|
| GRAPH-01 | EdGraph 类型检测 | test_detect_edgraph_export | test_graph_parsing.py | yes |
| GRAPH-02 | UEdGraph 基本信息提取 | test_read_ue_graph_basic | test_graph_parsing.py | yes |
| GRAPH-03 | UEdGraphNode 基类字段 | test_read_ue_graph_node_basic | test_graph_parsing.py | yes |
| GRAPH-04 | UEdGraphPin 完整结构 | test_read_ue_graph_pin_complete | test_graph_parsing.py | yes |
| GRAPH-05 | K2Node_CallFunction 解析 | test_k2node_call_function | test_graph_parsing.py | yes |
| GRAPH-06 | K2Node_Event 解析 | test_k2node_event | test_graph_parsing.py | yes |
| GRAPH-07 | K2Node_Knot 解析 | test_k2node_knot | test_graph_parsing.py | yes |
| GRAPH-08 | EdGraphNode_Comment 解析 | test_edgraph_node_comment | test_graph_parsing.py | yes |
| GRAPH-09 | K2Node_EnhancedInputAction 解析 | test_k2node_enhanced_input | test_graph_parsing.py | yes |
| GRAPH-10 | 引脚连接映射 | — | Phase 8 | deferred |

## Test File Structure

```
tests/test_graph_parsing.py
├── GRAPH-01: EdGraph 检测
│   ├── test_resolve_class_name_from_export()
│   ├── test_resolve_class_name_from_import()
│   └── test_detect_edgraph_export()
│
├── GRAPH-02: UEdGraph 基本信息
│   └ test_read_ue_graph_basic()
│
├── GRAPH-03: UEdGraphNode 基类
│   └── test_read_ue_graph_node_basic()
│
├── GRAPH-04: UEdGraphPin 完整结构
│   └── test_read_ue_graph_pin_complete()
│
├── GRAPH-05~09: 节点类型特定解析
│   ├── test_k2node_call_function()
│   ├── test_k2node_event()
│   ├── test_k2node_knot()
│   ├── test_edgraph_node_comment()
│   └── test_k2node_enhanced_input()
│
├── 集成测试
│   ├── test_full_graph_parsing_integration()
│   └── test_unknown_node_type_warning()
│
└── 边界测试
    ├── test_max_pins_limit()
    └── test_cooked_asset_skip()
```

## Test Fixtures Required

| Fixture | Purpose | Location |
|---------|---------|----------|
| create_test_archive | 合成二进制数据 | tests/conftest.py |
| mock_export | Mock ObjectExport | tests/test_graph_parsing.py |
| mock_import | Mock ObjectImport | tests/test_graph_parsing.py |

## Sampling Strategy

| Stage | Test Command | Coverage |
|-------|--------------|----------|
| Per task commit | `python -m pytest tests/test_graph_parsing.py -v -x` | New tests |
| Per wave merge | `python -m pytest tests/ -v` | Full suite |
| Phase gate | Full suite green + Lyra asset validation | 100% |

## Boundary Validation Tests

| Test | Boundary | Constant |
|------|----------|----------|
| test_max_pins_limit | pins_count | MAX_PINS_PER_NODE = 1000 |
| test_max_nodes_limit | nodes_count | MAX_NODES_PER_GRAPH = 5000 |
| test_max_linkedto_limit | linked_to_count | MAX_LINKEDTO_PER_PIN = 100 |
| test_cooked_asset_skip | PKG_Cooked | 0x200 flag check |

## Regression Tests

| Category | Tests | File |
|----------|-------|------|
| Phase 1 Core Parsing | 10 | test_uasset_read.py |
| Phase 2 Property Parsing | 3 | test_uasset_read.py |
| Phase 5 Boundary | 6 | test_uasset_read.py |
| Phase 6 Export Fix | 8 | test_uasset_read.py |

**Total regression:** 27 tests must pass before Phase 7 merge.

---

*Created: 2026-05-02 - Nyquist validation strategy for Phase 7*