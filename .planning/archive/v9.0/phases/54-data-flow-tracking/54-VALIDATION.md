# Phase 54: 数据流追踪 - Validation Architecture

**Phase:** 54-data-flow-tracking
**Created:** 2026-05-17
**Source:** RESEARCH.md Validation Architecture section

## Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | None（pytest auto-discovery） |
| Quick run command | `python -m pytest tests/test_output_formatting.py -x -k "data_flow"` |
| Full suite command | `python -m pytest tests/ -x` |

## Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Test Name |
|--------|----------|-----------|-------------------|-----------|
| DATA-01 | CallFunction input param data_source 追踪 | unit | `pytest tests/test_output_formatting.py -x -k "data_source"` | `test_trace_data_source_pure_function` |
| DATA-02 | Knot 链透明穿透 | unit | `pytest tests/test_output_formatting.py -x -k "knot_chain"` | `test_trace_data_source_knot_chain` |
| DATA-03 | SubPin 第一级展开 | unit | `pytest tests/test_output_formatting.py -x -k "sub_pin"` | `test_sub_pin_first_level_expand` |
| DATA-01 | Pure function data_providers 标注 | unit | `pytest tests/test_output_formatting.py -x -k "data_provider"` | `test_data_providers_pure_function` |
| DATA-01 | FunctionEntry 参数作为边界 | unit | `pytest tests/test_output_formatting.py -x -k "boundary"` | `test_trace_data_source_function_entry` |

## Plan → Test Coverage Map

| Plan | Tasks | Tests Covered |
|------|-------|---------------|
| 54-01 | Task 1: fixture 创建 | 所有测试依赖此 fixture |
| 54-01 | Task 2: 测试骨架 | 6 个测试骨架创建 |
| 54-02 | Task 1: DATA_BOUNDARY_NODES | `test_trace_data_source_function_entry` |
| 54-02 | Task 2: is_boundary_node | `test_trace_data_source_function_entry` |
| 54-02 | Task 3: _resolve_knot_chain | `test_trace_data_source_knot_chain` |
| 54-02 | Task 4: 启用测试 | 4 测试启用并验证 |
| 54-03 | Task 1: _trace_data_source | `test_trace_data_source_pure_function` |
| 54-03 | Task 2: _extract_call_function_parameters 增强 | `test_trace_data_source_pure_function` |
| 54-03 | Task 3: _trace_execution_from_event 增强 | `test_data_providers_pure_function` |
| 54-03 | Task 4: 启用剩余测试 | 所有测试通过 |

## Sampling Rate

- **Per task commit:** `python -m pytest tests/test_output_formatting.py -x -k "data_flow"`（相关测试）
- **Per wave merge:** `python -m pytest tests/ -x`（全量）
- **Phase gate:** 全量测试绿色 + Move 函数数据流验证（集成测试）

## Wave 0 Gaps (Pre-Execution)

- [x] `tests/fixtures/data_flow_fixture.py` — `sample_function_graph_with_data_flow` fixture（FunctionEntry + Knot + Pure + CallFunction）
- [x] `tests/test_output_formatting.py` — `test_trace_data_source_knot_chain` 测试骨架
- [x] `tests/test_output_formatting.py` — `test_trace_data_source_function_entry` 测试骨架
- [x] `tests/test_output_formatting.py` — `test_trace_data_source_pure_function` 测试骨架
- [x] `tests/test_output_formatting.py` — `test_sub_pin_first_level_expand` 测试骨架
- [x] `tests/test_output_formatting.py` — `test_data_providers_pure_function` 测试骨架
- [x] `tests/test_output_formatting.py` — `test_self_reference_as_boundary` 测试骨架

**Wave 0 创建 6 个测试 + 1 个 fixture。**

## Nyquist Compliance Check

- [x] Check 8a: Tests exist for each phase requirement
- [x] Check 8b: Tests cover all plan tasks
- [x] Check 8c: Sampling rate defined for each checkpoint
- [x] Check 8d: Wave 0 gaps identified and planned
- [x] Check 8e: VALIDATION.md exists (this file)

## Validation Commands

### Quick Validation (per task)
```bash
python -m pytest tests/test_output_formatting.py -x -k "data_flow"
```

### Full Validation (per wave)
```bash
python -m pytest tests/ -x
```

### Phase Gate Validation
```bash
python -m pytest tests/ -x --tb=short
```

## Test Fixture Structure

**Fixture: `sample_function_graph_with_data_flow`**

模拟 Move 函数图的数据流链：
- FunctionEntry_0 (Move) — 输出参数 "Forward/Backward" (double) → Knot 链
- K2Node_Knot_2 — 中继 "Left/Right" 数据
- K2Node_Knot_1 — 中继到 CallFunction
- K2Node_CallFunction_7445 (AddMovementInput) — 输入参数 ScaleValue (float)
- K2Node_CallFunction_8029 (GetActorForwardVector) — Pure function，输出 ReturnValue
- K2Node_CallFunction_7346 (AddMovementInput) — 输入参数 WorldDirection 连接 Pure function

Expected data flow paths:
1. FunctionEntry "Forward/Backward" → Knot_2 → Knot_1 → CallFunction_7445.ScaleValue
2. CallFunction_8029.ReturnValue → CallFunction_7346.WorldDirection
3. self → CallFunction_8029.Target (self reference)

---
**Created: 2026-05-17**
**Valid until: Phase 54 execution complete**