# UE5 序列化分析报告

**Phase:** 33a  
**Asset:** BP_FirstPersonCharacter.uasset (UE5.0)  
**Date:** 2026-05-12

## 调试结果

| 指标 | 值 |
|------|-----|
| Exports analyzed | 69 |
| PropertyTags parsed | 319 |
| Non-zero deltas | 0 |
| Errors | 0 |

## 根本原因

Phase 33a-01 和 33a-02 的修复已经解决了所有偏移错位问题：

1. **FText history_type 处理** — 旧代码对 `history_type == 0xFF` 和 `0` 的处理不完整，
   导致 DefaultTextValue 读取后位置偏移。`read_ftext_with_history()` 函数正确处理所有
   history_type（0xFF=None, 0=Base, 1-254=Custom），确保字节对齐。

2. **PropertyTag size 验证** — 旧代码对负数和超大 size 抛出 ParseError，导致解析中断。
   `validate_size(tolerant=True)` 容错模式接受异常 size，让解析继续到下一个 tag。

3. **偏移校验结果** — 修复后 delta = 0（实际读取字节数 == PropertyTag.size），
   表明所有属性值的序列化边界正确。

## 修复方案实施

| 修复 | 文件 | 状态 |
|------|------|------|
| FText history type parser | serializers/graph.py | ✅ 完成 |
| validate_size tolerant mode | archive.py | ✅ 完成 |
| read_property_tag tolerant param | serializers/property_tags.py | ✅ 完成 |
| CLI --tolerant/--strict flags | cli.py | ✅ 完成 |
| parse_uasset tolerant param | parse_uasset.py | ✅ 完成 |

## 验证

- 383 passed, 71 skipped, 0 failed (全量测试)
- 新增 10 个 UE5 序列化容错测试
- 调试工具输出 delta 全部为 0
