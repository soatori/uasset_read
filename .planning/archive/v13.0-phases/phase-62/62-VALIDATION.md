---
phase: 62
plan: 01
validation_version: 1
---

# Phase 62: 字节码 → 表达式树 — Validation

## Test Framework

- **Framework**: pytest
- **Test file**: `tests/test_kismet.py`
- **Run command**: `python -m pytest tests/test_kismet.py -xvs`

## Requirement → Test Mapping

| Requirement | Test Function(s) | Type | Status |
|-------------|-----------------|------|--------|
| BYTECODE-01: ScriptBytecode 提取 | `test_bytecode_extractor` | Unit | Planned |
| BYTECODE-01: ScriptBytecode 提取 | `test_extract_bytecode_from_uasset` | Integration | Planned |
| BYTECODE-02: FKismetArchive 增强 | `test_fkismet_archive_tolerant_mode` | Unit | Planned |
| BYTECODE-02: FKismetArchive 增强 | `test_parse_bytecode_to_expressions` | Integration | Planned |
| BYTECODE-02: FKismetArchive 增强 | `test_tolerant_mode_vs_strict_mode` | Unit | Planned |
| BYTECODE-03: 表达式列表输出 | `test_expression_output_formats` | Unit | Planned |

## Test Categories

### Unit Tests
- `test_fkismet_archive_tolerant_mode` — FKismetArchive 容错模式
- `test_bytecode_extractor` — extract_bytecode_bytes 和 parse_bytecode_stream
- `test_expression_output_formats` — expressions_to_flat_list 和 expressions_to_tree
- `test_tolerant_mode_vs_strict_mode` — 严格 vs 容错模式对比

### Integration Tests
- `test_extract_bytecode_from_uasset` — 从真实 .uasset 提取字节码
- `test_parse_bytecode_to_expressions` — 完整解析链路

## Acceptance Criteria

1. 所有测试通过：`python -m pytest tests/test_kismet.py -x`
2. BYTECODE-01: 能从 UFunction/Function 导出提取非空字节数组
3. BYTECODE-02: FKismetArchive tolerant 参数工作正常，parse_bytecode_stream 返回完整表达式列表
4. BYTECODE-03: 两种输出格式（flat list / tree）可正确序列化到 JSON
5. 容错模式下遇到未知 token 不崩溃，继续解析
6. 非 UStruct 导出安全跳过
