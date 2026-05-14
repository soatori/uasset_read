---
title: "35c-02: archive.py FString 长度验证（OOM 防护）"
plan_id: "35c-02"
phase: "35c"
subsystem: "security"
tags: [validation, bounds-check, fstring, oom-protection, CR-02]
dependencies:
  requires: []
  provides: [fstring-length-validation]
  affects: [archive.py, constants.py]
tech_stack:
  added: [MAX_FSTRING_LENGTH 常量, UTF-8 长度验证]
  patterns: [防御性编程]
key_files:
  created: []
  modified: [src/uasset_read/archive.py, src/uasset_read/constants.py, tests/test_uasset_read.py]
decisions:
  - 使用统一常量 MAX_FSTRING_LENGTH (10 MB) 替代硬编码值
  - UTF-8 和 UTF-16 字符串都使用相同上限
  - 错误消息格式统一为 "exceeds maximum {MAX_FSTRING_LENGTH}"
metrics:
  duration: "3 minutes"
  completed: "2026-05-13T03:15:00Z"
  tasks: 1
  files: 3
---

# Phase 35c Plan 02: FString 长度验证 Summary

在 `archive.py` 中添加 UTF-8 字符串长度验证，使用统一常量 `MAX_FSTRING_LENGTH`，修复 CR-02 OOM 防护问题。

## 完成任务

### Task 1: 添加 UTF-8 长度验证

**修改位置:**
- `constants.py`: 添加 `MAX_FSTRING_LENGTH = 10_000_000` (10 MB)
- `archive.py`: 导入 `MAX_FSTRING_LENGTH` 常量
- `archive.py:read_fstring()`: 对 UTF-8 字符串添加长度上限验证
- `archive.py:read_fstring()`: 使用统一常量替换硬编码 `10_000_000`

**验证测试:**
- UTF-8 字符串长度超过 10M → 正确抛出 ParseError
- UTF-16 字符串长度超过 10M → 正确抛出 ParseError
- 普通字符串 → 正常读取
- 测试套件 → 414 passed, 67 skipped

## 技术细节

| 验证点 | 阈值 | 错误消息格式 |
|--------|------|--------------|
| UTF-8 字符串长度 | > 10,000,000 | "UTF-8 string length {length} exceeds maximum {MAX_FSTRING_LENGTH}" |
| UTF-16 字符串长度 | > 10,000,000 | "UTF-16 string length {utf16_len} exceeds maximum {MAX_FSTRING_LENGTH}" |

**修改前后对比:**

```python
# 修改前 (UTF-16 有验证，UTF-8 无验证)
if length < 0:
    utf16_len = -length * 2
    if utf16_len > 10_000_000:  # 硬编码值
        raise ParseError(f"UTF-16 string length {utf16_len} too large")
    ...
data = self.read(length)  # 无验证！

# 修改后 (统一常量，两种情况都有验证)
if length < 0:
    utf16_len = -length * 2
    if utf16_len > MAX_FSTRING_LENGTH:
        raise ParseError(f"UTF-16 string length {utf16_len} exceeds maximum {MAX_FSTRING_LENGTH}")
    ...
if length > MAX_FSTRING_LENGTH:
    raise ParseError(f"UTF-8 string length {length} exceeds maximum {MAX_FSTRING_LENGTH}")
data = self.read(length)
```

## 偏差记录

### 自动修复 (Rule 2)

**1. 添加 UTF-8 长度验证测试**
- **发现位置:** 实现 UTF-8 验证时
- **问题:** 测试套件只有 UTF-16 overflow 测试，缺少 UTF-8 测试
- **修复:** 添加 `test_utf8_length_overflow` 测试
- **提交:** 1718145

**2. 更新错误消息格式**
- **发现位置:** UTF-16 测试期望 "too large"
- **问题:** 计划指定错误消息格式为 "exceeds maximum"
- **修复:** 更新测试断言匹配新错误消息格式
- **提交:** 1718145

## 测试状态

- UTF-8 overflow 测试: 通过
- UTF-16 overflow 测试: 通过
- 完整测试套件: 414 passed, 67 skipped

## Self-Check: PASSED

- 文件已修改: `src/uasset_read/archive.py`, `src/uasset_read/constants.py`, `tests/test_uasset_read.py`
- 提交已创建: `1718145`
- 验证测试通过
- 真实资产解析正常