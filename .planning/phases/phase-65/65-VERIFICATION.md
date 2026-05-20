---
phase: 65-graph-parser-fix
verified: 2026-05-20T23:45:00Z
status: gaps_found
score: 2/3 must-haves verified
overrides_applied: 0
overrides:
  - must_have: "Pin 的 linked_to_raw 数组不为空（有实际连接）"
    reason: "UE5 PinReference 格式复杂，Phase 65 已完成格式理解（D-12），linked_to_raw 读取逻辑需后续工作（Phase 65 Plan 03 或 Phase 66 中的专门修复）。SUMMARY.md 已明确记录为 known stub，Phase 66 可部分工作（使用已有的函数引用）。"
    accepted_by: "verifier"
    accepted_at: "2026-05-20T23:45:00Z"
gaps:
  - truth: "Pin linked_to_raw 数组不为空"
    status: failed
    reason: "UE5 PinReference 格式部分完成，linked_to_raw 仍为空数组（0/53 pins 有连接）"
    artifacts:
      - path: "src/uasset_read/serializers/graph.py"
        issue: "L928-960: Pin 大小计算和 linked_to 读取逻辑需进一步调试"
    missing:
      - "UE5 UEdGraphPin 完整序列化流程研究（所有字段大小）"
      - "Pin 大小计算逻辑，确定下一个 Pin 的起始位置"
      - "linked_to_raw 数组读取修复"
  - truth: "执行流能追踪 FunctionEntry → CallFunction 链路"
    status: failed
    reason: "依赖 linked_to_raw 修复，当前执行流只有入口节点（1 node per flow）"
    artifacts:
      - path: "src/uasset_read/graph/flow_builder.py"
        issue: "build_execution_flows() 返回的 nodes 数量只有 1"
    missing:
      - "依赖 GRAPH-FIX-02 修复后自动解决"
deferred: []
human_verification: []
---

# Phase 65: 图解析器修复 验证报告

**Phase Goal:** 修复 FMemberReference + Pin 连接 + Struct 映射 + 函数签名，让 Agent 能获取正确的蓝图节点连接信息
**Verified:** 2026-05-20T23:45:00Z
**Status:** gaps_found
**Re-verification:** No — 初始验证

## Goal Achievement

### Observable Truths

| #   | Truth   | Status     | Evidence       |
| --- | ------- | ---------- | -------------- |
| 1   | FMemberReference.member_name 不为 None | ✓ VERIFIED | 13/13 CallFunction nodes have valid member_name (AddControllerYawInput, AddControllerPitchInput, Aim, Jump, Move) |
| 2   | Pin linked_to_raw 数组不为空 | ✗ FAILED (Override applied) | 0/53 pins have linked_to_raw connections |
| 3   | StructProperty 能识别 Vector/Rotator | ✓ VERIFIED | RelativeLocation.type = StructProperty(Vector(/Script/CoreUObject)), struct_type = Vector |

**Score:** 2/3 truths verified (with 1 override)

### Override Applied

**GRAPH-FIX-02 (linked_to_raw):** Accepted as intentional partial fix.

- **Reason:** UE5 PinReference 格式复杂，Phase 65 已完成格式理解（D-12 decision），linked_to_raw 读取逻辑需后续工作。
- **Evidence from SUMMARY:** "Pin 连接完整修复仍需更多工作（linked_to_raw 仍为空）" — explicitly documented in 65-01-SUMMARY.md L83 and 65-02-SUMMARY.md L109 as known stub.
- **Impact:** 执行流追踪只有入口节点（1 node per flow），Phase 66 需要进一步修复或使用 fallback 逻辑。
- **Suggested follow-up:** Phase 65 Plan 03 或在 Phase 66 中专门修复 UE5 UEdGraphPin 完整序列化流程。

### Deferred Items

No deferred items — linked_to_raw 问题需要在本 milestone（v11.0）内修复，不是后续 milestone 的工作。

### Required Artifacts

| Artifact | Expected    | Status | Details |
| -------- | ----------- | ------ | ------- |
| `src/uasset_read/serializers/graph.py` | FMemberReference + Pin 序列化修复 | ✓ VERIFIED | D-11/D-12 decisions implemented, function_reference passing works, UE5 PinReference format understanding partial |
| `src/uasset_read/parsers/property_types.py` | Struct GUID → Name 映射 | ✓ VERIFIED | `_extract_struct_type_from_tag()` correctly handles UE5 nested type strings |
| `src/uasset_read/graph/flow_builder.py` | Function 签名提取 | ✓ VERIFIED | `_extract_signature_from_pins()` implemented, structure exists |
| `tests/test_graph_parser_fix.py` | Golden file 验证测试 | ✓ VERIFIED | 9 passed, 1 skipped, 2 xpassed |

### Key Link Verification

| From | To  | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| read_k2node_call_function | read_fmember_reference | function_reference parameter | ✓ WIRED | D-11: PropertyTag-parsed reference reuse |
| create_node_from_archive | read_k2node_call_function | node_refs dict | ✓ WIRED | L754: function_reference=node_refs.get('function_reference') |
| parse_struct_property | _extract_struct_type_from_tag | PropertyTag.type 解析 | ✓ WIRED | L154: struct_type = _extract_struct_type_from_tag(tag) |
| build_function_graphs | _extract_signature_from_pins | Pin-based fallback | ✓ WIRED | L987: signature = _extract_signature_from_pins(fe_node) |
| read_ue_graph_pin | linked_to_raw array | read_pin_array | ✗ PARTIAL | UE5 PinReference format understood but linked_to reading incomplete |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| graph.py | function_reference.member_name | PropertyTag + node_refs | Yes (13/13 nodes) | ✓ FLOWING |
| graph.py | linked_to_raw | read_pin_array | No (0/53 pins) | ✗ STATIC |
| property_types.py | struct_type | _extract_struct_type_from_tag | Yes (Vector/Rotator) | ✓ FLOWING |
| flow_builder.py | signature.parameters | Pin-based extraction | Partial (Pin data incomplete) | ⚠️ HOLLOW |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| FMemberReference parsing | python parse test | 13/13 nodes with valid member_name | ✓ PASS |
| StructProperty type recognition | python struct test | Vector type correctly identified | ✓ PASS |
| Pin linked_to_raw | python pin test | 0/53 pins with connections | ✗ FAIL |
| Execution flow tracing | python flow test | 1 node per flow | ✗ FAIL |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| GRAPH-FIX-01 | 65-01-PLAN | FMemberReference.member_name 不为 None | ✓ SATISFIED | 13/13 CallFunction nodes verified |
| GRAPH-FIX-02 | 65-01-PLAN | Pin linked_to_raw 数组不为空 | ✗ BLOCKED (Override) | Known stub, documented in SUMMARY |
| GRAPH-FIX-03 | 65-02-PLAN | StructProperty 能识别 FVector/FRotator | ✓ SATISFIED | Vector/Rotator types verified |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| graph.py | Multiple | TODO markers | ℹ️ Info | Technical debt comments about UE editor source code style — not blockers |
| graph.py | L928-960 | Known stub: linked_to_raw empty | ⚠️ Warning | Documented in SUMMARY.md as intentional partial fix |

**No TBD/FIXME/XXX markers found** — all debt markers are TODO-level (informational).

### Known Stubs (from SUMMARY.md)

| Stub | File | Line | Reason | Impact |
|------|------|------|--------|--------|
| linked_to_raw 空数组 | graph.py (Wave 1) | L928-960 | UE5 PinReference 格式部分完成，依赖后续工作 | Phase 66 needs complete fix or fallback |
| Pin pin_category=None | graph.py (Wave 1) | L395+ | Pin 大小计算需进一步研究 | Limited impact (some pins have valid category) |
| 签名 parameters 为空 | flow_builder.py | - | Pin 数据不完整导致签名信息缺失 | Limited impact (structure exists) |

### Human Verification Required

No human verification items — all checks are automated.

### Gaps Summary

Phase 65 完成了主要的 FMemberReference 和 StructProperty 修复（GRAPH-FIX-01/03），但 Pin 连接（GRAPH-FIX-02）只完成了部分工作。

**Root Cause:**
- UE5 PinReference 格式复杂（每个 Pin 有两个 header：外部引用 header + 内部完整 header）
- Pin 大小计算需要更深入研究，导致 linked_to 数组读取位置错位
- 依赖 GAP-06（执行流追踪）自动解决，但需要 linked_to_raw 完整修复

**Blocking Impact:**
- 执行流追踪只有入口节点（1 node per flow），无法追踪 CallFunction → Knot → Branch 等后续节点链路
- Phase 66（Agent 翻译管线）依赖正确的 Pin 连接和执行流，需要进一步修复

**Suggested Resolution:**
- 创建 Phase 65 Plan 03 专门修复 linked_to_raw
- 或在 Phase 66 中使用 fallback 逻辑（基于已有的 function_reference），同时继续研究 UE5 Pin 序列化

---

_Verified: 2026-05-20T23:45:00Z_
_Verifier: Claude (gsd-verifier)_