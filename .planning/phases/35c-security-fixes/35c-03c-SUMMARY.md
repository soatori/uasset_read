---
title: "35c-03c: object_resources.py 计数与偏移验证"
plan_id: "35c-03c"
phase: "35c"
subsystem: "security"
tags: [validation, bounds-check, object-resources, CR-05]
dependencies:
  requires: [35c-03a, 35c-03b]
  provides: [object-resources-validation]
  affects: [serializers/object_resources.py]
tech_stack:
  added: [负数验证, 范围检查]
  patterns: [防御性编程]
key_files:
  created: []
  modified: [src/uasset_read/serializers/object_resources.py]
decisions:
  - 使用常量 MAX_IMPORT_COUNT/MAX_EXPORT_COUNT (1,000,000) 作为上限
  - 负数值立即抛出 ParseError，防止后续代码处理无效数据
metrics:
  duration: "2 minutes"
  completed: "2026-05-13T02:36:00Z"
  tasks: 1
  files: 1
---

# Phase 35c Plan 03c: ObjectResources 计数与偏移验证 Summary

在 `object_resources.py` 中添加了 import/export 计数和 serial offset/size 的负数验证，修复 CR-05 安全问题。

## 完成任务

### Task 1: 添加验证逻辑

**修改位置:**
- `read_import_map()` 开头: 添加 `import_count` 负数和上限验证
- `read_export_map()` 开头: 添加 `export_count` 负数和上限验证
- `read_export_map()` 循环内: 添加 `serial_size`/`serial_offset` 负数验证
- `read_export_map()` 循环内: 添加 `script_serial_offset`/`script_serial_size` 负数验证

**验证测试:**
- 负数 `import_count` → 正确抛出 ParseError
- 负数 `export_count` → 正确抛出 ParseError
- 超限 `import_count` → 正确抛出 ParseError
- 超限 `export_count` → 正确抛出 ParseError
- 真实资产解析 → 不受影响，正常工作

## 技术细节

| 验证点 | 阈值 | 错误消息 |
|--------|------|----------|
| import_count | < 0 或 > 1,000,000 | 负数导入计数 / 超过最大值 |
| export_count | < 0 或 > 1,000,000 | 负数导出计数 / 超过最大值 |
| serial_size | < 0 | 导出 serial_size 为负数 |
| serial_offset | < 0 | 导出 serial_offset 为负数 |
| script_serial_offset | < 0 | 导出 script_serial_offset 为负数 |
| script_serial_size | < 0 | 导出 script_serial_size 为负数 |

## 偏差记录

### 自动修复 (Rule 2)

**1. 添加上限验证**
- **发现位置:** 实现 import_count/export_count 验证时
- **问题:** 计划只提到负数验证，但常量文件已有 MAX_IMPORT_COUNT/MAX_EXPORT_COUNT
- **修复:** 同时添加上限验证，防止内存耗尽攻击
- **提交:** b48598b

## 测试状态

- 新增验证逻辑: 通过
- 真实资产解析: 通过
- 现有测试套件: 2 个预存在失败（Phase 21, UTF-16 测试），非本次修改引入

## Self-Check: PASSED

- 文件已修改: `src/uasset_read/serializers/object_resources.py`
- 提交已创建: `b48598b`
- 验证测试通过
- 真实资产解析正常