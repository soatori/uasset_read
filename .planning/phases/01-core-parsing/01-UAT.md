---
status: testing
phase: 01-core-parsing
source: [01-01-SUMMARY.md]
started: 2026-04-28T12:30:00Z
updated: 2026-04-28T13:00:00Z
---

## Current Test

number: 2
name: Version validation fix
expected: |
  UE5_VERSION_MIN 应接受真实 UE5 文件（版本 500+），而非硬编码 1000
awaiting: pending fix verification

## Tests

### 1. Parse real UE5 .uasset file
expected: 解析 Lyra Character_Default.uasset 成功，返回正确的 Summary 和 NameMap
result: issue
reported: "版本验证错误：UE5Version=522 被拒绝（代码要求>=1000），修复后 NameOffset 解析错误（偏移值异常大1701736270）"
severity: blocker
diagnosis: LegacyFileVersion=-7 格式与 -8 不同，名称表结构变化

### 2. Version validation fix
expected: UE5_VERSION_MIN 应接受真实 UE5 文件（版本 500+），而非硬编码 1000
result: [pending]

### 3. Byte-swapping detection
expected: 解析器能正确检测和处理字节交换（通过魔术标签检测）
result: pass
note: Tag 正确读取为 0x9e2a83c1

### 4. Asset class identification
expected: get_asset_class() 能正确识别导出的资产类名
result: blocked
blocked_by: parser
reason: "解析失败，无法测试"

## Summary

total: 4
passed: 1
issues: 1
pending: 2
skipped: 0

## Gaps

- truth: "给定任意有效 .uasset 文件，解析器读取文件头后 PackageFileSummary 包含正确的魔术标签、版本号和偏移"
  status: failed
  reason: "Lyra 文件 UE5Version=522 被错误拒绝；修复版本后 NameOffset 解析错误"
  severity: blocker
  test: 1
  artifacts: []
  missing: ["LegacyFileVersion=-7/-7 格式支持"]
  diagnosis: "D-04 版本验证逻辑错误：UE5_VERSION_MIN=1000 不匹配实际 UE5 版本号（521-522）；文件头结构对 LegacyFileVersion=-7 需特殊处理"