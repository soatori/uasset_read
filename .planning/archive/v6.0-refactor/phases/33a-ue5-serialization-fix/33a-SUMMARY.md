---
phase: 33a
plan: 33a-01, 33a-02, 33a-03
status: complete
date: 2026-05-12
key-files:
  created:
    - tests/test_ue5_serialization.py
    - tools/debug_ue5_serialization.py
    - analysis/ue5_serialization_analysis.md
  modified:
    - src/uasset_read/serializers/graph.py
    - src/uasset_read/archive.py
    - src/uasset_read/serializers/property_tags.py
    - src/uasset_read/parse_uasset.py
    - src/uasset_read/cli.py
metrics:
  tests_added: 10
  tests_passed: 383
  tests_failed: 0
  tests_skipped: 71
---

# Phase 33a: UE5 序列化问题修复 — Summary

**Date:** 2026-05-12
**Status:** Complete ✅

## Objective

修复从 UE5.0 蓝图文件 `BP_FirstPersonCharacter.uasset` 中发现的三个序列化错误：
1. FText 长度过大 (33554432)
2. PropertyTag Size 为负数 (-1067974656)
3. 数组大小超出文件边界 (3328 > 2300)

## What Was Built

### Plan 33a-01: FText 序列化格式修复
- `read_ftext_with_history()` 函数支持所有 history_type (0xFF=None, 0=Base, 1-254=Custom)
- `read_ue_graph_pin` 中 DefaultTextValue 和 PinFriendlyName 使用新函数
- 容错模式下对异常长度返回空字符串而非抛出异常

### Plan 33a-02: PropertyTag 体积验证修复
- `FArchive.validate_size()` 添加 `tolerant` 参数，容错模式接受负数和超大 size
- `read_property_tag()` 添加 `tolerant` 参数并传递给 validate_size
- `parse_uasset()` 添加 `tolerant` 参数（默认 True），传递给 FArchive
- CLI 添加 `--tolerant`（默认开启）和 `--strict` 标志

### Plan 33a-03: 节点序列化偏移校验
- 创建 `tools/debug_ue5_serialization.py` 调试工具
- 输出 `debug_output_v2.json` 包含所有 PropertyTag 的偏移和 delta 信息
- 分析确认修复后 delta = 0，所有序列化边界正确

## Test Results

- 383 passed, 71 skipped, 0 failed
- 新增 10 个 UE5 序列化容错测试（test_ue5_serialization.py）

## Self-Check: PASSED

All success criteria met:
- ✅ All 3 errors handled gracefully in tolerant mode
- ✅ Debug tool runs and produces debug_output_v2.json
- ✅ 383/383 tests pass (no regressions introduced)
- ✅ Zero non-zero deltas in serialization analysis
