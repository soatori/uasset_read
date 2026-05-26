---
phase: 71
plan: 01
subsystem: graph
tags: [execution-flow, chain-expression, n2c, json-format]
requires: [CHAIN-01, CHAIN-02]
provides: [build_execution_chains, execution_chains-format]
affects: [formatters, n2c, graph]
tech_stack:
  added: [graph/chain_builder.py]
  patterns: [chain-expression, deprecation-warning]
key_files:
  created:
    - src/uasset_read/graph/chain_builder.py
  modified:
    - src/uasset_read/graph/__init__.py
    - src/uasset_read/graph/flow_builder.py
    - src/uasset_read/formatters/text_formatter.py
    - src/uasset_read/formatters/markdown_formatter.py
    - src/uasset_read/formatters/helpers.py
    - src/uasset_read/n2c/__init__.py
    - src/uasset_read/n2c/serializer.py
    - src/uasset_read/__init__.py
    - tests/test_output_formatting.py
    - tests/test_phase21_verification.py
    - tests/test_skill_integration.py
decisions:
  - D-01: JSON output field execution_flows → execution_chains
  - D-02: build_execution_chains() returns {start_event, chains[], has_cycle}
  - D-03: Branch nodes split chains at branch points
  - D-04: chain_builder.py extracted from n2c/flow_extractor.py
  - D-05: chain_metadata optional field for branch_count, etc.
  - D-06: All formatters adapted to chain format
  - D-07: build_execution_flows() deprecated with DeprecationWarning
metrics:
  duration: ~30min
  tasks: 5 waves
  files_modified: 12
  commits: 6
  tests_passed: 1290
---

# Phase 71 Plan 01: 执行流链式表达 Summary

将执行流输出从逐对连接 `{"from": "...", "to": "..."}` 升级为链式字符串 `"N1->N2->N3"`，提供更简洁的 LLM 优化格式。

## Wave 执行记录

| Wave | 任务 | Commit | 说明 |
|------|------|--------|------|
| 1 | chain_builder.py | e05e2ae | 新增 build_execution_chains() API |
| 2 | JSON 输出格式 | 1e04ac2 | execution_flows → execution_chains |
| 3 | Consumer 适配 | 179d56d | text/markdown/helpers 适配 |
| 4 | Deprecation | 378dc50 | build_execution_flows() deprecated |
| 5 | Tests | 9a8af81, 0f41f8a | 测试更新 |

## 交付物

### 1. build_execution_chains() API (`graph/chain_builder.py`)

```python
from uasset_read import build_execution_chains

chains = build_execution_chains(graph)
# 返回: [{"start_event": "Event.BeginPlay", "chains": ["N0->N1->N2"], "has_cycle": false}]
```

### 2. JSON 输出格式变更

- `format_graphs_json()`: `"execution_flows"` → `"execution_chains"`
- `build_graphs_summary()`: 同上

### 3. Consumer 适配

- `text_formatter.py`: 直接展示链式字符串
- `markdown_formatter.py`: `_build_mermaid_flowchart_from_chains()` 从 chains 解析
- `helpers.py`: schema info 更新

### 4. N2C 兼容

- `n2c/__init__.py`: `extract_chains` 别名指向 `build_execution_chains_from_flows`
- `n2c/serializer.py`: 导入改为 `graph/chain_builder`

### 5. Deprecation

- `build_execution_flows()` 添加 `DeprecationWarning`
- 推荐使用 `build_execution_chains()` 替代

## 偏离记录

### 自动修复（Rule 3）

**[Rule 3 - Blocking] 测试更新**
- **问题**: 测试期望 `execution_flows` 字段，Phase 71 替换为 `execution_chains`
- **修复**: 更新 test_output_formatting.py、test_phase21_verification.py、test_skill_integration.py 中的相关断言
- **Commit**: 9a8af81, 0f41f8a

### 跳过的测试（非 Phase 71 相关）

`test_skill_integration.py` 中 19 个测试失败，涉及 skill/knowledge/examples 目录缺失。这些是预先存在的问题，与 Phase 71 无关。

## Self-Check: PASSED

- [x] chain_builder.py 存在
- [x] build_execution_chains 可导入
- [x] build_execution_flows deprecated warning 正常
- [x] 1290 tests passed

---

*Phase 71 Plan 01 完成*
*Date: 2026-05-22*