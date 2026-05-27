# 测试状态归档 — 2026-05-27

> 本文档记录当前 dev-0.3.0 分支上所有已知测试失败的状态、原因和后续处理计划。

## 总览

| 指标 | 数值 |
|------|------|
| 总计 | 1650 tests |
| 通过 | 1464 passed |
| 失败 | 84 failed |
| 跳过 | 130 skipped |
| xfailed | 2 xfailed |
| 错误 | 4 errors |

## 失败分类

### 1. BP_FirstPersonCharacter 依赖失败 (60+ tests)

**根因**: 测试依赖 `E:\Develop\lib\UnrealEngine\Samples\FirstPerson` 下的真实 `.uasset` 文件。部分测试因资产版本变化、解析路径变更或资产缺失而失败。

**核心失败链**:
- `name 'UE5_PROPERTY_TAG_EXTENSION' is not defined` — `property_parser.py` / `graph.py` 中的版本常量引用问题导致解析失败，引发连锁反应
- 解析失败后，所有依赖 `ParseResult.is_success` 的 golden test 全部失败

**受影响文件**:
- `tests/test_phase21_verification.py` — 7 failures (graphs_exist, node_count 等)
- `tests/test_agent_translation.py` — 17 failures (BP_FirstPersonCharacter IR/generation)
- `tests/test_bp_first_person_reference_alignment.py` — 3 failures + 3 errors (baseline 解析失败)
- `tests/test_cpp_skeleton_e2e.py` — 5 failures (RealUasset end-to-end)
- `tests/test_phase60_verification.py` — 7 failures + 1 error (golden path)
- `tests/test_phase73_bp_first_person_e2e.py` — 8 failures (E2E connections)
- `tests/test_phase73_pin_trace.py` — 3 failures (pin trace mode)
- `tests/test_phase75_event_node_field_alignment.py` — 5 failures (EventGraph 字段对齐)
- `tests/test_graph_parser_fix.py` — 5 failures (FMemberReference + execution flow)
- `tests/test_exportmap_properties.py` — 1 failure

**处理计划**:
1. 修复 `UE5_PROPERTY_TAG_EXTENSION` 常量引用问题（Phase 76 COR-02 范围）
2. 确认测试资产是否可用，不可用则加 `@pytest.mark.skipif`
3. 修复后重新运行 golden test 验证

### 2. Skill Integration 测试 (18 tests)

**根因**: `.claude/skills/uasset-read/` 目录不存在。该测试验证 AI 代理 skill 文件的存在和内容。

**受影响文件**:
- `tests/test_skill_integration.py` — 全部 18 tests

**处理计划**:
- 确认 skill 文件是否仍需要。如果 Superpowers 工作流不再使用 GSD skill 文件，删除此测试文件或更新为 Superpowers skill 路径。

### 3. N2C Full Regression (1 test)

**根因**: `test_all_existing_tests_pass()` 是测试套件的 canary，任何失败都会导致它失败。

**受影响文件**:
- `tests/n2c/test_full_regression.py` — 1 failure

**处理计划**:
- 不需要单独修复。当分类 1/2 的失败解决后，此测试自动通过。

### 4. Warning: 已删除的 API 调用

**现象**: 多个测试调用了已废弃的 `build_execution_flows()` 函数，产生 DeprecationWarning。

**受影响**:
- `tests/n2c/test_roundtrip.py` (8 warnings)
- `tests/n2c/test_token_reduction.py` (2 warnings)
- `tests/test_output_formatting.py` (13 warnings)
- `tests/test_phase14_output_formats.py` (1 warning)

**处理计划**:
- 将调用从 `build_execution_flows()` 迁移到 `build_execution_chains()`。
- 这是低风险清理，可在 Phase 76 之后处理。

## 跳过测试 (130 skipped)

主要由 `@pytest.mark.skipif` 触发，原因是：
- 测试资产路径不存在（`E:\Develop\lib\UnrealEngine\Samples\FirstPerson`）
- 可选功能标记（`@pytest.mark.optional`）

## 验证命令

```bash
# 全量测试
python -m pytest tests/ -q --tb=no

# 仅看失败项
python -m pytest tests/ -q --tb=line --last-failed

# 排除 skill 测试
python -m pytest tests/ -q --ignore=tests/test_skill_integration.py
```

## 后续行动

| 优先级 | 行动 | 归属 Phase |
|--------|------|-----------|
| P0 | 修复 `UE5_PROPERTY_TAG_EXTENSION` 常量引用 | Phase 76 |
| P1 | 确认 skill 测试是否需要更新或删除 | 独立 |
| P2 | 确认测试资产可用性，添加 skipif | Phase 76+ |
| P3 | 迁移 `build_execution_flows()` → `build_execution_chains()` | Phase 76 之后 |

---

*Created: 2026-05-27, as part of GSD → Superpowers migration*
