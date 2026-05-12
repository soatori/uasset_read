---
status: complete
phase: 33-entry-test-adapt
source: [33-01-SUMMARY.md, 33-02-SUMMARY.md, 33-03-SUMMARY.md]
started: 2026-05-12T10:00:00Z
updated: 2026-05-12T10:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running process. Clear __pycache__, run `python -m uasset_read --help` from fresh. Command returns exit code 0, displays help text without import errors or stack traces.
result: pass

### 2. CLI Entry Point Works
expected: `uasset-read --help`或`python -m uasset_read --help`返回退出码0，显示完整的argparse帮助文本，包含所有格式选项(--json/--text/--summary/--markdown)、--verbose、--output、--export、--graph、--schema。
result: pass

### 3. parse_uasset() Function Works
expected: `from uasset_read import parse_uasset`成功导入。对测试UAsset文件调用parse_uasset()返回ParseResult对象，包含exports数组、errors为空或包含可预期的警告，不抛出未捕获异常。
result: pass

### 4. Module Imports Work Correctly
expected: 以下导入全部成功且无副作用：
- `from uasset_read import parse_uasset, __version__`
- `from uasset_read import format_json_full, format_text_summary, format_markdown`
- `from uasset_read.graph import extract_blueprint_graphs, build_execution_flows`
- `from uasset_read.constants import CPF_Edit, CPF_BlueprintVisible, CPF_ZeroConstructor`
- `__version__`等于"6.0.0"
result: pass

### 5. All Tests Pass
expected: 运行`pytest tests/`返回373 passed, 0 failed, 71 skipped（或更多passed，0 failed）。所有测试通过 implies Phase 33迁移成功。
result: pass

### 6. Old File Removed
expected: `uasset_read.py`文件不存在。任何尝试`from uasset_read_legacy import parse_uasset`应失败（不支持旧版单文件导入）。
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0

## Gaps

[none - all tests passed]
