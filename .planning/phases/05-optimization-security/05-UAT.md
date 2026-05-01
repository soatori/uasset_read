---
status: testing
phase: 05-optimization-security
source: 05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md, 05-04-SUMMARY.md
started: 2026-05-01T12:00:00Z
updated: 2026-05-01T12:00:00Z
---

## Current Test

number: 1
name: 大文件 mmap 自动启用
expected: |
  解析一个 >50MB 的 .uasset 文件时，ParseResult.mmap_used 应为 True。如无此类大文件可测试，可用 --verbose 或检查源码确认 MMAP_THRESHOLD=50MB 常量存在。
awaiting: user response

## Tests

### 1. 大文件 mmap 自动启用
expected: 解析 >50MB 文件时 mmap_used=True，或确认 MMAP_THRESHOLD=50MB 常量存在
result: pending

### 2. mmap 失败自动回退
expected: mmap 初始化失败时自动回退到普通文件读取，解析继续成功，mmap_warning 包含警告信息
result: pending

### 3. 损坏文件边界验证
expected: 提供包含无效偏移的损坏文件时，产生清晰错误消息而非崩溃或静默错误
result: pending

### 4. 无效属性大小捕获
expected: PropertyTag.Size 无效时，validate_size() 拒绝并产生错误，包含属性名和大小信息
result: pending

### 5. 解析器不挂起
expected: 损坏文件（如循环结构异常）不应导致解析器无限循环，应在合理时间内完成或报错
result: pending

### 6. 部分结果返回
expected: 文件部分损坏时，ParseResult 应包含已成功解析的部分数据，errors/warnings 记录问题位置
result: pending

### 7. 警告分类
expected: 非致命错误（如跳过损坏属性）记录在 warnings 列表，致命错误记录在 errors，两者分离
result: pending

### 8. 错误上下文信息
expected: 错误消息应包含 ErrorContext 信息：offset（文件位置）、phase（解析阶段）、operation（操作类型）
result: pending

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Gaps

[none yet]