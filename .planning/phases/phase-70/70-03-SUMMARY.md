---
phase: 70-n2cstruct-schema
plan: "03"
subsystem: n2c
tags: [validation, json-schema, n2c, zero-dependency]
dependency_graph:
  requires: ["70-01"]
  provides: ["N2C_JSON_SCHEMA", "validate_n2c_json()"]
  affects: ["n2c module exports"]
tech-stack:
  added: ["纯 Python JSON Schema 验证引擎"]
  patterns: ["递归验证、类型检查、模式匹配、枚举验证"]
key-files:
  created:
    - "src/uasset_read/n2c/validation.py"
    - "tests/n2c/test_validation.py"
  modified:
    - "src/uasset_read/n2c/__init__.py"
decisions:
  - "使用纯 Python 递归验证而非 jsonschema 库（零外部依赖要求）"
  - "Schema 定义为不可变模块级常量，防止运行时篡改（T-70-SC）"
  - "非 dict 输入直接返回防御性错误（T-70-06）"
metrics:
  duration_minutes: 15
  completed: "2026-05-22"
  tests_added: 27
  tests_total_n2c: 109
  lines_validation: 210
  lines_tests: 280
---

# Phase 70 Plan 03: N2C JSON Schema 验证 Summary

**一-liner:** 实现 N2CStruct JSON Schema 定义和纯 Python 验证函数（零外部依赖），确保 N2C 输出格式稳定性和可消费性。

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | 定义 N2C JSON Schema + validate_n2c_json() | b87ca14 | validation.py, test_validation.py, __init__.py |

## Verification Results

- `python -m pytest tests/n2c/test_validation.py -x -q`: **27 passed**
- `python -m pytest tests/n2c/ -x -q`: **109 passed** (27 new + 82 existing)
- `from uasset_read.n2c import validate_n2c_json, N2C_JSON_SCHEMA`: 导入成功
- 所有 6 个行为验证场景通过

## Key Implementation Details

### N2C_JSON_SCHEMA
- Draft-07 兼容的 JSON Schema dict
- 覆盖全部 N2CStruct 字段：version, metadata, graphs, structs, enums
- $defs 复用：n2c_node, n2c_pin, n2c_flows
- 模式约束：version (semver `\d+\.\d+\.\d+`), node.id (`N\d+`)
- 枚举约束：graph_type (EventGraph/Function/Macro/Animation), pin.direction (input/output)

### validate_n2c_json(data: dict) -> list[str]
- 防御性检查：非 dict 输入直接返回错误 (T-70-06)
- 递归验证引擎：_validate_object / _validate_array / _validate_value
- 类型检查：string, integer, number, boolean, array, object
- 特殊处理：Python bool 是 int 子类，JSON Schema 中 integer 不接受 boolean
- 模式检查：compiled regex cache
- $ref 解析：`#/$defs/definition_name` 格式

### 测试覆盖
- Schema 结构验证 (4 tests)
- 有效输入验证 (3 tests)
- 非 dict 输入防御 (3 tests)
- 顶层 required 字段 (5 tests)
- 版本格式验证 (3 tests)
- Graph 验证 (3 tests)
- Node 验证 (4 tests)
- Pin 验证 (2 tests)

## Deviations from Plan

None - plan executed exactly as written.

## Auth Gates

None.

## Known Stubs

None.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: input_validation | src/uasset_read/n2c/validation.py | validate_n2c_json 对非 dict 输入返回防御性错误 (T-70-06) |

## Self-Check: PASSED

- [x] src/uasset_read/n2c/validation.py 存在
- [x] tests/n2c/test_validation.py 存在
- [x] src/uasset_read/n2c/__init__.py 已更新
- [x] 27 个验证测试全部通过
- [x] 109 个 n2c 测试全部通过
- [x] validate_n2c_json 和 N2C_JSON_SCHEMA 可从 n2c 模块导入
- [x] Commit b87ca14 存在
