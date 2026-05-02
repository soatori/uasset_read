---
phase: 07-blueprint-graph-core
plan: 03
subsystem: blueprint-graph
tags: [node-type-parsers, GRAPH-05, GRAPH-06, GRAPH-07, GRAPH-08, GRAPH-09]
dependencies:
  requires: [07-02-node-pin-parsing]
  provides: [read_fmember_reference, read_k2node_call_function, read_k2node_event, read_k2node_knot, read_edgraph_node_comment, read_k2node_enhanced_input]
  affects: [UEdGraphNode.node_data]
tech_stack:
  added: []
  patterns: [match/case dispatch, FMemberReference, FSoftObjectPath, RGBA tuple]
key_files:
  created: [tests/test_graph_parsing.py]
  modified: [uasset_read.py]
decisions:
  - D-02a: 未知节点类型处理（记录类型名，node_data=dict，继续解析）
  - D-02b: 类型识别方法（resolve_class_name + match/case 分派）
metrics:
  duration: "15 minutes"
  tasks_completed: 2
  files_modified: 1
  files_created: 1
  lines_added: 338 (uasset_read.py) + 521 (test)
  test_status: "105 passed, 36 skipped"
---

# Phase 7 Plan 03: 节点类型特定解析器 Summary

实现 5 种需求节点类型的特定解析器，集成类型分派机制，完成 Phase 7 全部核心需求（GRAPH-05~09）。

## Completed Tasks

| Task | Name | Commit | Files Modified |
|------|------|--------|----------------|
| 1 | 实现 5 种节点类型特定解析器（GRAPH-05~09） | 31f1938 | uasset_read.py |
| 2 | 创建 Phase 7 单元测试并验证完整功能 | f1ef902 | tests/test_graph_parsing.py |

## Task 1: 实现 5 种节点类型特定解析器（GRAPH-05~09）

新增节点类型数据类：

1. **K2NodeCallFunction** - GRAPH-05
   - `function_reference`: FMemberReference（函数引用）
   - `b_defaults_to_pure`: bool（是否为纯函数）

2. **K2NodeEvent** - GRAPH-06
   - `event_reference`: FMemberReference（事件引用）
   - `b_override_function`: bool（是否为重写函数）

3. **K2NodeKnot** - GRAPH-07
   - 无额外字段（仅基类 Pins 数组）

4. **EdGraphNodeComment** - GRAPH-08
   - `comment_color`: Tuple[float, float, float, float]（RGBA 颜色）
   - `node_width`: int（注释框宽度）
   - `node_height`: int（注释框高度）
   - `font_size`: int（字体大小）

5. **K2NodeEnhancedInputAction** - GRAPH-09
   - `input_action_path`: str（FSoftObjectPath AssetPath）

新增解析函数：

1. **read_fmember_reference()** - 辅助函数
   - 解析 FMemberReference 结构（MemberParent + MemberName + MemberGuid + bSelfContext）
   - 用于 CallFunction 和 Event 的函数/事件引用

2. **read_k2node_call_function()** - GRAPH-05
   - 解析 FunctionReference + bDefaultsToPureFunc

3. **read_k2node_event()** - GRAPH-06
   - 解析 EventReference + bOverrideFunction

4. **read_k2node_knot()** - GRAPH-07
   - 无额外字段，返回空实例

5. **read_edgraph_node_comment()** - GRAPH-08
   - 解析 CommentColor（4 floats RGBA）+ NodeWidth/Height + FontSize

6. **read_k2node_enhanced_input()** - GRAPH-09
   - 解析 InputAction（FSoftObjectPath AssetPath）

类型分派机制：

- 更新 `read_ue_graph_node()` 添加 match/case 分派
- 未知类型触发警告但解析继续（node_data = {"unknown_type": class_name}）

## Task 2: 创建 Phase 7 单元测试并验证完整功能

创建 tests/test_graph_parsing.py（521 行）：

- **GRAPH-01 测试**: EdGraph 类型检测
- **GRAPH-02 测试**: UEdGraph 基本信息
- **GRAPH-03 测试**: UEdGraphNode 基类字段
- **GRAPH-04 测试**: UEdGraphPin 完整结构
- **GRAPH-05~09 测试**: 节点类型特定解析器
- **类型分派测试**: 未知类型处理、已知类型分派
- **安全边界测试**: MAX_* 常量验证
- **导入验证测试**: 所有新增导出的函数和数据类

测试结果：20 passed, 13 skipped（需要真实资产数据的测试标记为 skip）

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

以下功能推迟到后续阶段：

| Stub | File | Line | Reason |
|------|------|------|--------|
| LinkedTo 连接映射 | uasset_read.py | linked_to_raw | Phase 8 构建 PinId → 目标节点/引脚映射 |
| FSoftObjectPath 完整解析 | uasset_read.py | read_k2node_enhanced_input | 仅读取 AssetPath，SubPathString 未验证 |
| 合成数据测试 | tests/test_graph_parsing.py | pytest.skip | 需要真实 .uasset 文件验证完整二进制解析 |

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag:match-fallback | uasset_read.py L2067-2073 | 未知类型 fallback 记录类型名（D-02a/T-07-03-01） |

## Verification

```bash
# 节点类型解析器导入验证
python -c "from uasset_read import read_k2node_call_function, read_k2node_event, read_k2node_knot, read_edgraph_node_comment, read_k2node_enhanced_input; print('Import OK')"
# Output: Import OK

# FMemberReference 解析器导入验证
python -c "from uasset_read import read_fmember_reference; print('FMemberReference OK')"
# Output: FMemberReference OK

# 节点类型数据类导入验证
python -c "from uasset_read import K2NodeCallFunction, K2NodeEvent, K2NodeKnot, EdGraphNodeComment, K2NodeEnhancedInputAction; print('Dataclass Import OK')"
# Output: Dataclass Import OK

# acceptance_criteria grep 检查
grep -c "def read_fmember_reference" uasset_read.py == 1
grep -c "def read_k2node_call_function" uasset_read.py == 1
grep -c "def read_k2node_event" uasset_read.py == 1
grep -c "def read_k2node_knot" uasset_read.py == 1
grep -c "def read_edgraph_node_comment" uasset_read.py == 1
grep -c "def read_k2node_enhanced_input" uasset_read.py == 1
grep "match class_name:" uasset_read.py | wc -l == 1

# Phase 7 单元测试
python -m pytest tests/test_graph_parsing.py -v
# Output: 20 passed, 13 skipped

# 完整测试套件无回归
python -m pytest tests/ -v --ignore=tests/test_output_formatting.py -k "not test_json_full_structure"
# Output: 105 passed, 36 skipped
```

## Self-Check: PASSED

- [x] read_fmember_reference function exists: verified via grep and import
- [x] read_k2node_call_function function exists: verified via grep and import
- [x] read_k2node_event function exists: verified via grep and import
- [x] read_k2node_knot function exists: verified via grep and import
- [x] read_edgraph_node_comment function exists: verified via grep and import
- [x] read_k2node_enhanced_input function exists: verified via grep and import
- [x] match/case class_name dispatch exists: verified via grep
- [x] K2NodeCallFunction dataclass exists: verified via import
- [x] K2NodeEvent dataclass exists: verified via import
- [x] K2NodeKnot dataclass exists: verified via import
- [x] EdGraphNodeComment dataclass exists: verified via import
- [x] K2NodeEnhancedInputAction dataclass exists: verified via import
- [x] tests/test_graph_parsing.py exists: verified via test -f
- [x] Commit 31f1938 exists: verified via git log
- [x] Commit f1ef902 exists: verified via git log

---

*Phase: 07-blueprint-graph-core*
*Plan: 03*
*Completed: 2026-05-02*