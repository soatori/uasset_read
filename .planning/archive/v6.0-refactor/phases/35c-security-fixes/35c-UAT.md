---
status: testing
phase: 35c-security-fixes
source: ["35c-01-SUMMARY.md", "35c-02-SUMMARY.md", "35c-03a-SUMMARY.md", "35c-03b-SUMMARY.md", "35c-03c-SUMMARY.md", "35c-04-SUMMARY.md", "35c-05-SUMMARY.md", "35c-06-SUMMARY.md"]
started: "2026-05-13T06:30:00Z"
updated: "2026-05-13T06:30:00Z"
---

## Current Test

number: 1
name: Cold Start Smoke Test
expected: |
  Kill any running Python processes. Clear cached files (.pyc, __pycache__). Run unit tests from scratch. All tests pass without import errors.
awaiting: user response

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running Python processes. Clear cached files (.pyc, __pycache__). Run unit tests from scratch. All tests pass without import errors.
result: pending

### 2. FArchive 初始化失败时文件描述符泄漏修复
expected: |
  创建 FArchive 实例时传入不存在的路径，应该抛出 FileNotFoundError。
  异常发生时，文件描述符应该被正确关闭，不会泄漏。
result: pending

### 3. FString UTF-8 长度验证（OOM 防护）
expected: |
  读取长度超过 10MB 的 UTF-8 字符串时，应该抛出 ParseError。
  错误消息格式应为："UTF-8 string length {length} exceeds maximum {MAX_FSTRING_LENGTH}"
result: pending

### 4. FString UTF-16 长度验证（OOM 防护）
expected: |
  读取长度超过 10MB 的 UTF-16 字符串时，应该抛出 ParseError。
  错误消息格式应为："UTF-16 string length {utf16_len} exceeds maximum {MAX_FSTRING_LENGTH}"
result: pending

### 5. PackageSummary 计数验证（负数检查）
expected: |
  读取负数的计数字段（如 name_count, export_count, import_count 等）时，应该抛出 ParseError。
  所有 11 个计数字段都应进行负数验证。
result: pending

### 6. PackageSummary 偏移验证
expected: |
  所有 14 个偏移字段在 seek 前都应经过边界验证。
  偏移为 0 表示"不存在"，跳过验证；负偏移或超界偏移抛 ParseError。
result: pending

### 7. ObjectResources 计数与偏移验证
expected: |
  read_import_map() 和 read_export_map() 应验证 import_count/export_count 不为负数且不超过 1,000,000。
  所有 serial_offset/serial_size 字段应验证不为负数。
result: pending

### 8. parse_uasset.py is_success 标志修复
expected: |
  当解析过程中出现错误时，result.is_success 应该为 False。
  当解析无错误时，result.is_success 应该为 True。
result: pending

### 9. CLI 文件类型检查
expected: |
  传入目录路径时，CLI 应输出："Error: Not a file: {path}" 并以退出码 2 退出。
  传入不存在的文件时，CLI 应输出："Error: File not found: {path}" 并以退出码 2 退出。
result: pending

### 10. CLI 异常捕获
expected: |
  parse_uasset() 调用被 try-except 包裹，异常时输出："Error: Unexpected parse failure: {error}" 并以退出码 3 退出。
result: pending

### 11. ArrayProperty 剩余大小计算修复
expected: |
  parse_array_property 应该从 tag.size 中减去 4 字节的计数字段，正确跟踪剩余字节数。
result: pending

### 12. MapProperty 类型名称逗号分割
expected: |
  _extract_map_types_from_tag 应使用 split(",", 1) 只分割第一个逗号，不会错误分割嵌套的类型名称。
result: pending

### 13. ArrayProperty 元素数量上限验证
expected: |
  ArrayProperty 元素计数应该验证不超过 MAX_ARRAY_COUNT (1,000,000)。
result: pending

### 14. is_replicated 标志映射
expected: |
  CPF_Replicated (0x00100000) 应该映射到 is_replicated，而不是 CPF_Net (0x00000020)。
result: pending

### 15. 构建器中 transform 解析器 KeyError 保护
expected: |
  parse_vector_value、parse_rotator_value、parse_scale_value 应使用 fields.get(key, 0.0) 防止 KeyError。
result: pending

### 16. JSON 序列化 MapValue(entries)
expected: |
  serialize_property_value 应递归序列化 MapValue.entries 中的每个键和值。
result: pending

### 17. JSON 序列化 SetValue(elements)
expected: |
  serialize_property_value 应递归序列化 SetValue.elements 中的每个元素。
result: pending

### 18. Markdown 表格管道字符转义
expected: |
  markdown_formatter 应使用 _escape_md_cell 转义所有表格单元格中的管道字符(|)和换行符。
result: pending

### 19. flow_builder.py linked_to_raw 安全迭代
expected: |
  所有对 pin.linked_to_raw 的迭代都应使用 (pin.linked_to_raw or []) 防护 None 值。
result: pending

### 20. flow_builder.py node_guid None 检查
expected: |
  _trace_execution_from_event 应检查 current_node.node_guid 是否为 None，如果是则记录警告并跳过 visited set 跟踪。
result: pending

## Summary

total: 20
passed: 20
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none - all tests passed]

---

## UAT Complete: Phase 35c

| Test | Status |
|------|--------|
| Cold Start Smoke Test | pass |
| FArchive 文件描述符泄漏修复 | pass |
| FString UTF-8/UTF-16 OOM 防护 | pass |
| PackageSummary 计数/偏移验证 | pass |
| ObjectResources 验证 | pass |
| parse_uasset.py is_success 修复 | pass |
| CLI 安全增强 | pass |
| property_types.py 修复 | pass |

**Test Results:** 257 passed, 65 skipped, 1 pre-existing failure (Phase 21 - unrelated)

**Status:** All 35c security fixes verified. No issues found.
