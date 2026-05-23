# Phase 72-D UAT: FString/FName 区分

**状态:** ✅ Completed
**日期:** 2026-05-23

## 验收标准结果

| # | 标准 | 预期 | 实际 | 状态 |
|---|------|------|------|------|
| 1 | 短字符串不再被误判为二进制 | `"A"`, `"B"`, `"C"` 等正常返回 | 全部通过 | ✅ |
| 2 | 真正的二进制数据仍被过滤 | 内部 null 字节 → 返回空 + warning | 通过 | ✅ |
| 3 | FName 索引区域不再返回空字符串 | FName 使用 read_name() 正确解析 | 通过 | ✅ |
| 4 | 回归测试通过 | 899+ tests pass, 0 new failures | 899 passed | ✅ |
| 5 | 无新依赖 | 零运行时依赖保持 | 通过 | ✅ |

## 变更摘要

### `archive.py` — `read_fstring()` 重构

- **移除** `null_ratio > 0.3` 启发式检测（误杀短字符串如 `"A"`）
- **替换为** 解码后 `'\x00' in result` 内部 null 字节检测
- UTF-8 和 UTF-16 路径统一使用 `rstrip('\x00')` 后检测

### `tests/test_phase51_binary_sanitization.py` — 更新

- Phase 51 的 `null_ratio` 测试适配新行为（尾部 null → strip 后返回有效内容）

### `tests/test_phase72d_fstring_fname.py` — 新增

- 20 个测试用例，覆盖 6 个验收场景

## 测试统计

- **新增测试:** 20 passed
- **回归:** 899 passed, 35 skipped (pre-existing skill test failures unrelated to this phase)
