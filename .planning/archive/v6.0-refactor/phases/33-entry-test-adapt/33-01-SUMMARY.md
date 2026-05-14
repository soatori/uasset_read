---
phase: 33
plan: 01
type: execute
subsystem: entry-test-adapt
tags: [migration, parsing, api]
dependency:
  requires: [Phase 31, Phase 32]
  provides: ["parse_uasset() function", "transform data classes", "transform parsers", "BPGC finder", "CPF constants"]
  affects: ["src/uasset_read/__init__.py", "uasset_read_legacy.py shim removal"]
tech-stack:
  added: [models/transforms.py, blueprint/transform_parser.py, parse_uasset.py]
  patterns: [dataclass, factory, error-handling, try-except-finally]
key-files:
  created:
    - src/uasset_read/parse_uasset.py
    - src/uasset_read/models/transforms.py
    - src/uasset_read/blueprint/transform_parser.py
  modified:
    - src/uasset_read/__init__.py
    - src/uasset_read/serializers/object_resources.py
    - src/uasset_read/serializers/graph.py
    - src/uasset_read/constants.py
    - src/uasset_read/parsers/property_types.py
    - src/uasset_read/blueprint/variable_extractor.py
    - src/uasset_read/blueprint/__init__.py
    - src/uasset_read/models/__init__.py
    - src/uasset_read/serializers/__init__.py
decisions:
  - "Removed legacy shim from __init__.py, replacing with direct module imports"
  - "Changed read_k2node_* functions to return dicts instead of model objects (fix Rule 1)"
  - "Fixed extract_blueprint_metadata signature to match parse_uasset caller (fix Rule 1)"
  - "parse_property_flags_to_labels uses semantic mapping (Edit→EditAnywhere) matching legacy behavior"
  - "format_variable_type migrated to parsers/property_types.py for type-formatting coherence"
metrics:
  duration: "~20min"
  completed: "2026-05-12T00:00:00Z"
---

# Phase 33 Plan 01: 入口与测试适配 Summary

**One-liner:** 创建 `parse_uasset()` 主解析管线，补齐所有迁移缺口函数（转换数据类、变换解析、BPGC 查找、CPF 常量、PropertyFlags 解析），删除旧版兼容 shim，版本号升级至 6.0.0。

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | 创建 models/transforms.py | 07c67e3 | transforms.py, models/__init__.py |
| 2 | 创建 blueprint/transform_parser.py | c5cdc73 | transform_parser.py, blueprint/__init__.py |
| 3 | 创建 parse_uasset.py + BPGC + __init__.py | 7bb364d | parse_uasset.py, object_resources.py, __init__.py, serializers/__init__.py |
| 4 | 补齐剩余 shim 函数 | 49850ff | constants.py, property_types.py, variable_extractor.py, graph.py, __init__.py, blueprint/__init__.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] extract_blueprint_metadata 签名不匹配**
- **Found during:** Task 3 verification (test_skill_integration)
- **Issue:** 现有函数签名为 `(properties, export_map)` 但 parse_uasset 调用 6 个参数
- **Fix:** 重写函数接受 `(export, archive, import_map, export_map, name_map, summary)` 参数
- **Files modified:** src/uasset_read/blueprint/variable_extractor.py

**2. [Rule 1 - Bug] read_k2node_* 返回模型对象缺少必填字段**
- **Found during:** Task 4 verification (parse_uasset on test asset)
- **Issue:** read_k2node_call_function 等返回 K2NodeCallFunction 等模型对象，但缺少 node_guid 必填参数
- **Fix:** 改为返回 Dict 而非模型对象，因为它们在 create_node_from_archive 中作为 node_data 使用
- **Files modified:** src/uasset_read/serializers/graph.py
- **Commit:** 49850ff

**3. [Rule 1 - Bug] parse_property_flags_to_labels 语义映射错误**
- **Found during:** Task 4 verification (test_phase12)
- **Issue:** 直接标志→标签映射不匹配，CPF_Edit 应映射为 "EditAnywhere" 而非 "Edit"
- **Fix:** 重写为语义映射逻辑（Edit+EditConst→EditConst, Edit alone→EditAnywhere, BlueprintVisible+ReadOnly→BlueprintReadOnly）
- **Files modified:** src/uasset_read/blueprint/variable_extractor.py
- **Commit:** 49850ff

**4. [Rule 2 - Security/Missing] CPF_* 常量缺失**
- **Found during:** Task 4 (constants.py review)
- **Issue:** constants.py 缺少 CPF_* 属性标志位常量
- **Fix:** 追加 25 个 CPF_* 常量（CPF_Edit 到 CPF_NonPIEDuplicateTransient）
- **Files modified:** src/uasset_read/constants.py

**5. [Rule 3 - Blocking] format_variable_type 函数缺失**
- **Found during:** Task 4 (test imports)
- **Issue:** tests/test_phase12 需要 format_variable_type，但旧版 shim 删除后不存在
- **Fix:** 从 uasset_read_legacy.py 等价迁移到 parsers/property_types.py
- **Files modified:** src/uasset_read/parsers/property_types.py

## Known Stubs

None — all functions in this plan are fully implemented with real logic, no placeholder values.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: input_validation | parse_uasset.py | .uasset 文件输入通过三层 try/except 处理（VersionError/ParseError/Exception） |
| threat_flag: error_disclosure | parse_uasset.py | 错误信息包含文件路径和解析上下文，输出到 result.errors |
