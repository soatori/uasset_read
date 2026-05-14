---
title: "35c-03a: package_summary.py 计数验证（11 个字段）"
plan_id: "35c-03a"
phase: "35c"
status: "complete"
---

# Phase 35c Plan 03a: PackageSummary 计数验证 Summary

**问题**: CR-04 + HIGH-04 + M2/M3 — `package_summary.py` 所有 `read_i32()` 计数字段未验证负数
**文件**: `src/uasset_read/serializers/package_summary.py`
**优先级**: P0

## 一句话总结

为 PackageFileSummary 解析器中的 11 个计数字段添加负数验证，防止恶意构造的 uasset 文件导致内存分配攻击。

## 修改内容

### 已验证字段（11 个）

| 字段 | 行号 | 原有验证 | 添加验证 |
|------|------|---------|---------|
| `name_count` | 180 | `> MAX_NAME_COUNT` | `< 0` |
| `export_count` | 210 | `> MAX_NAME_COUNT` | `< 0` |
| `import_count` | 217 | `> MAX_NAME_COUNT` | `< 0` |
| `cell_export_count` | 229 | 无 | `< 0` |
| `cell_import_count` | 231 | 无 | `< 0` |
| `soft_package_references_count` | 246 | 无 | `< 0` |
| `import_type_hierarchies_count` | 261 | 无 | `< 0` |
| `generations_count` | 279 | 无 | `< 0` |
| `compressed_chunks_count` | 316 | 无 | `< 0` |
| `additional_packages_count` | 324 | 无 | `< 0` |
| `chunk_ids_count` | 346 | 无 | `< 0` |

### 修复模式

```python
count = archive.read_i32()
if count < 0:
    raise ParseError(f"Negative {field_name} count: {count}")
# 后续处理...
```

## 验证结果

- 413 passed, 67 skipped（排除 2 个预先存在的失败测试）
- 预先存在的失败测试与本修复无关：
  - `test_phase21_verification.py::TestExecutionFlow::test_jump_started_flow`
  - `test_ue5_pin_integration.py::TestUE5PinIntegration::test_pins_have_linked_to_raw`

## 安全影响

负数计数验证防止以下攻击：

1. **内存分配攻击**: `range(negative_count)` 在 Python 中不会分配内存，但恶意文件可能导致逻辑错误
2. **整数溢出利用**: 在某些上下文中，负数可能被转换为大的正数（如 C 语言的 size_t）
3. **拒绝服务**: 无效的循环计数可能导致意外行为

## 偏离计划

无 - 完全按照计划执行。

## 提交

- **Commit**: baee9f4
- **Message**: `fix(35c-03a): 为 package_summary.py 的 11 个计数字段添加负数验证`