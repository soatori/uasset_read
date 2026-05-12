---
wave: 3
plan: 32-03
status: complete
created: 2026-05-12
---

# 32-03 SUMMARY: 测试适配与模块集成

## 完成内容

1. **修复 build_status_info 返回类型**
   - 返回 `StatusInfo` dataclass 而非 `Dict`
   - 符合 test_phase14_output_formats.py 的属性访问测试

2. **更新 json_formatter.py**
   - `format_json_full`: 使用 `asdict(build_status_info(result))`
   - `format_json_summary`: 同上

3. **更新 markdown_formatter.py**
   - 使用 `status_info.status` 和 `status_info.message` 属性访问

4. **修复测试格式兼容**
   - `test_graphs_summary_calls_format`: 适配 Phase 31 新格式 (start_event + nodes)
   - 验证 `nodes` 中包含 `K2Node_CallFunction` 类型节点

## 验证

- 107 passed, 25 skipped ✓
- `test_status_success_when_no_errors` ✓
- `TestStatusField::test_status_info_*` ✓
- `test_graphs_summary_calls_format` ✓

## Commit

- `ee11fc7` — feat(32-03): test adaptation and module integration