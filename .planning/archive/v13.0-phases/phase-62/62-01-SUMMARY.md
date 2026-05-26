---
phase: 62
plan: "01"
type: execute
subsystem: kismet
tags: [bytecode, expression, extractor, tolerant-mode]
completed: 2026-05-20
dependency_graph:
  requires: ["Phase 61: Kismet 表达式系统 (FKismetArchive, EXPR_CLASS_MAP)"]
  provides: ["BYTECODE-01: ScriptBytecode 提取", "BYTECODE-02: FKismetArchive 容错模式", "BYTECODE-03: 表达式列表输出"]
  affects: ["src/uasset_read/kismet/archive.py", "src/uasset_read/kismet/bytecode_extractor.py", "src/uasset_read/kismet/__init__.py"]
tech-stack:
  added: ["bytecode_extractor module"]
  patterns: ["TDD (RED/GREEN)", "stream exhaustion loop (CUE4Parse UStruct.cs pattern)"]
key-files:
  created:
    - "src/uasset_read/kismet/bytecode_extractor.py"
    - "tests/test_kismet.py"
  modified:
    - "src/uasset_read/kismet/archive.py"
    - "src/uasset_read/kismet/__init__.py"
decisions:
  - "extract_bytecode_bytes requires archive, export, summary, name_map, import_map, export_map parameters for full context"
  - "Integration tests gracefully skip when test assets lack UStruct bytecode"
  - "expressions_to_tree scans both to_dict() values and instance attributes for nested expressions"
metrics:
  duration_minutes: ~30
  tests: 6
  tests_passed: 4
  tests_skipped: 2
  commits: 6
---

# Phase 62 Plan 01: 字节码→表达式树 提取和解析入口

**One-liner:** 实现 ScriptBytecode 字节流提取和解析入口，增强 FKismetArchive 支持容错模式，新增 bytecode_extractor 模块提供从 UStruct 导出中提取字节码并解析为 KismetExpression 列表的完整链路。

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| Wave 0 | 创建测试脚手架 | `bb65ec6` | `tests/test_kismet.py` |
| Task 1 | 增强 FKismetArchive 容错模式 | `66a9517` | `src/uasset_read/kismet/archive.py` |
| Task 2 | 创建 bytecode_extractor 模块 | `94e7fda` | `src/uasset_read/kismet/bytecode_extractor.py` |
| Task 3 | 更新 kismet 模块导出 | `93d22c5` | `src/uasset_read/kismet/__init__.py` |
| Task 4 | 表达式列表输出 API | `55c4fff` | `src/uasset_read/kismet/bytecode_extractor.py` |
| Task 5 | 端到端集成测试 | `a81d722` | `tests/test_kismet.py` |

## Decisions Made

1. **extract_bytecode_bytes 参数设计：** 需要 archive (FArchive)、export (ObjectExport)、summary (PackageFileSummary)、name_map、import_map、export_map 六个参数，以提供完整的序列化上下文和类型识别能力。

2. **测试资产限制：** 当前 FirstPerson 示例蓝图的 Function 导出没有实际字节码（script_serial_size 仅包含属性终止符），集成测试设计为 graceful skip。

3. **expressions_to_tree 递归策略：** 同时扫描 to_dict() 输出值和实例属性以检测嵌套 KismetExpression，避免重复。

## Deviations from Plan

None - plan executed exactly as written.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: bounds_validation | `bytecode_extractor.py` | serializedScriptSize 验证 < export.script_serial_size (T-62-02) |
| threat_flag: whitelist_filtering | `bytecode_extractor.py` | USTRUCT_TYPES 白名单验证，拒绝未知类型 (T-62-01) |
| threat_flag: loop_termination | `archive.py` | 容错模式 10 次连续未知 token 终止循环 (T-62-05) |

## Verification

- `python -m pytest tests/test_kismet.py -v`: 4 passed, 2 skipped
- `from uasset_read.kismet import extract_bytecode_bytes, parse_bytecode_stream, extract_and_parse`: OK
- `FKismetArchive(data, name, name_map, tolerant=True)`: OK
- No stubs found in created/modified files

## Self-Check: PASSED

All created files exist, all commits verified.
