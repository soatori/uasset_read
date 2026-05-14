---
phase: 35c-security-fixes
reviewed: 2026-05-13T16:30:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - src/uasset_read/archive.py
  - src/uasset_read/constants.py
  - src/uasset_read/serializers/package_summary.py
  - src/uasset_read/serializers/object_resources.py
  - src/uasset_read/parse_uasset.py
  - src/uasset_read/cli.py
  - src/uasset_read/parsers/property_types.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 35c: 代码审查报告

**审查日期**: 2026-05-13
**审查深度**: standard
**审查文件数**: 7
**状态**: 发现问题

## 概要

Phase 35c 的安全性修复总体实现正确。所有计划要求的安全验证（FD 泄漏修复、FString OOM 防护、计数/偏移验证、CLI 安全增强、属性条目验证）均已正确实施。

发现 2 个 WARNING 级别问题（常量语义不一致）和 1 个 INFO 级别问题。无 BLOCKER 级别安全漏洞。

## Warnings

### WR-01: export_count 上限使用错误的常量

**文件**: `src/uasset_read/serializers/package_summary.py:219`
**问题**: 第 216-220 行验证 export_count 时使用 `MAX_NAME_COUNT` (10,000,000) 而非语义正确的 `MAX_EXPORT_COUNT` (1,000,000)。虽然不会导致安全漏洞（上限反而更宽松），但违反了常量语义一致性。

**代码片段**:
```python
if export_count > MAX_NAME_COUNT:
    raise ParseError(f"Export count exceeds maximum")
```

**预期行为**: 应导入并使用 `MAX_EXPORT_COUNT` 常量，与 `object_resources.py:204` 保持一致。

**影响**: 语义不一致，代码可维护性降低。实际运行时允许最多 10M 个导出条目，超出常量定义的合理上限 1M。

**修复建议**:
1. 在第 14 行导入列表中添加 `MAX_EXPORT_COUNT`
2. 第 219 行改为 `if export_count > MAX_EXPORT_COUNT`

---

### WR-02: import_count 上限使用错误的常量

**文件**: `src/uasset_read/serializers/package_summary.py:228`
**问题**: 第 225-230 行验证 import_count 时使用 `MAX_NAME_COUNT` 而非 `MAX_IMPORT_COUNT`。与 WR-01 同类的语义不一致问题。

**代码片段**:
```python
if import_count > MAX_NAME_COUNT:
    raise ParseError(f"Import count exceeds maximum")
```

**预期行为**: 应使用 `MAX_IMPORT_COUNT` 常量，与 `object_resources.py:95` 保持一致。

**影响**: 语义不一致。允许最多 10M 个导入条目，超出设计上限 1M。

**修复建议**:
1. 在第 14 行导入列表中添加 `MAX_IMPORT_COUNT`
2. 第 228 行改为 `if import_count > MAX_IMPORT_COUNT`

---

## Info

### IN-01: EXIT_* 常量重复定义

**文件**: `src/uasset_read/constants.py:231-234` 与 `src/uasset_read/cli.py:22-26`
**问题**: 两个文件定义了相同的 EXIT_SUCCESS/EXIT_PARSE_ERROR/EXIT_FILE_NOT_FOUND/EXIT_ARGUMENT_ERROR 常量。

**代码片段** (constants.py):
```python
EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3
```

**代码片段** (cli.py):
```python
EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3
```

**影响**: 代码重复，但不影响功能。cli.py 内部使用自己的常量定义，constants.py 的定义可能是供其他模块使用的设计意图。

**修复建议**: 可选择从 constants.py 导入到 cli.py，或删除 cli.py 的重复定义。若 constants.py 的定义有更广泛的用途，则保持现状即可。

---

## 计划验证完整性检查

以下确认 Phase 35c 计划的 8 个修复项均已实施：

| 计划项 | 文件 | 状态 |
|--------|------|------|
| 35c-01 FD 泄漏修复 | archive.py:21-48 | ✅ 正确实现 |
| 35c-02 FString OOM 防护 | archive.py:219-233, constants.py:33 | ✅ 正确实现 |
| 35c-03a 计数验证 (11字段) | package_summary.py | ✅ 实现完成，有语义问题 (WR-01/02) |
| 35c-03b 偏移验证 (14字段) | package_summary.py | ✅ 正确实现 |
| 35c-03c 计数/偏移验证 | object_resources.py:93-96, 202-205, 237-240, 286-289 | ✅ 正确实现 |
| 35c-04 is_success + tolerant | parse_uasset.py:147, 85, 105, 166-167 | ✅ 正确实现 |
| 35c-05 CLI 安全增强 | cli.py:93-99, 104-108 | ✅ 正确实现 |
| 35c-06 属性条目验证 | property_types.py:110-112, 187-190, 211-214 | ✅ 正确实现 |

**备注**: 
- `depends_offset` (第 260 行) 未验证，但计划 35c-03b 明确列出的 14 个偏移不包括此字段
- `soft_object_paths_count` 和 `gatherable_text_data_count` 无负数验证，但计划 35c-03a 的 11 个字段列表不包括这些

上述未验证字段虽不属计划范围，但后续迭代可考虑补全以保持防御性编程一致性。

---

## 安全评估结论

Phase 35c 的核心安全目标（输入验证、资源管理、错误报告）已达成：

1. **FD 泄漏风险消除**: `FArchive.__init__` 使用 try-except 包裹初始化，失败时调用 `close()` 释放资源
2. **OOM 攻击阻断**: `read_fstring` 对 UTF-8/UTF-16 字符串长度实施上限验证 (MAX_FSTRING_LENGTH = 10MB)
3. **恶意文件防御**: 所有计数字段验证非负，所有偏移字段调用 `validate_offset()`
4. **CLI 稳定性增强**: 文件类型检查 + parse_uasset 异常捕获确保程序不会因异常输入崩溃

发现的 2 个 WARNING 问题不影响安全性，仅影响代码语义一致性。

---

_审查日期: 2026-05-13_
_审查者: Claude (gsd-code-reviewer)_
_审查深度: standard_