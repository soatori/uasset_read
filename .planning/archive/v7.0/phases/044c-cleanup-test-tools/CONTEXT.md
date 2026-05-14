# Phase 44c: 清理测试工具

## Status
⏳ 待执行

## Goal
清空所有废弃/调试测试文件，重建干净的测试环境。

## Scope

### 删除
- `tests/test_property_parsing.py` — 已标记 DEPRECATED，整个模块跳过
- `tools/` 下全部调试脚本（14+ 个文件）
- `temp/` 下全部调试文件（28 个文件）

### 保留
- `tools/` 和 `temp/` 目录本身（已在 .gitignore 中排除）

## Success Criteria
- `tools/` 和 `temp/` 目录为空
- `tests/test_property_parsing.py` 已删除
- 所有剩余测试通过，无回归

## Dependencies
- Phase 44b 完成

## Notes
执行后验证 `python -m pytest tests/ -v` 全部通过。

*Created: 2026-05-14*
