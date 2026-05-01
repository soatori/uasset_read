---
status: complete
phase: 01-core-architecture
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md]
started: 2026-05-01T17:15:00Z
updated: 2026-05-01T17:25:00Z
---

## Current Test

[testing complete]

## Tests

### 1. 验证常量值与 UE 源码一致
expected: 导入 constants.py，检查 PACKAGE_FILE_TAG、PACKAGE_FILE_TAG_SWAPPED、最低版本常量值正确
result: pass

### 2. FPackageIndex 类型判断
expected: 创建 FPackageIndex(0) → is_null=True; FPackageIndex(1) → is_export=True; FPackageIndex(-1) → is_import=True
result: pass

### 3. 打开有效 .uasset 文件
expected: 使用 UAssetArchive.open(path) 打开测试文件，自动检测字节序，不抛出异常
result: pass

### 4. 魔数验证失败
expected: 打开无效文件（魔数错误）抛出 MagicError，包含 expected 和 actual 值
result: pass

### 5. 解析 FPackageFileSummary
expected: 解析测试文件，获取 UE4/UE5 双版本号、NameCount/ExportCount/ImportCount 偏移正确
result: pass

### 6. CustomVersion 解析
expected: 解析 CustomVersionContainer，已知 GUID 映射到正确名称，未知 GUID 显示 "Unknown-{guid}"
result: pass

### 7. FString 读取
expected: read_fstring() 正确读取 UTF-8 和 UTF-16 编码的 UE FString
result: pass

### 8. 100+ GUID 映射覆盖
expected: CUSTOM_VERSION_GUIDS 字典包含 >= 100 条目
result: pass

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Gaps

[none]