# Phase 17 Deferred Issues

**发现的预先存在问题，不在当前计划范围内修复。**

## Issue 1: ObjectExport ScriptSerializationOffset 字段读取顺序错误

**发现时间:** Plan 17-03 执行期间验证 UE 5.7 资产解析

**问题描述:**
- 代码读取顺序（uasset_read.py 第 2199-2200 行）:
  ```python
  script_serial_size = archive.read_i64()  # 声明为 size，读取第一个字段
  script_serial_offset = archive.read_i64()  # 声明为 offset，读取第二个字段
  ```
- UE 源码序列化顺序（ObjectResource.cpp 第 215-216 行）:
  ```cpp
  Record << SA_VALUE(TEXT("ScriptSerializationStartOffset"), E.ScriptSerializationStartOffset);  // 第一个
  Record << SA_VALUE(TEXT("ScriptSerializationEndOffset"), E.ScriptSerializationEndOffset);  // 第二个
  ```

**根因分析:**
- UE 先序列化 StartOffset，后序列化 EndOffset
- 代码先读取第一个字段赋值给 `script_serial_size`（语义上应该是 EndOffset），后读取第二个字段赋值给 `script_serial_offset`（语义上应该是 StartOffset）
- 这导致：
  - `script_serial_offset` 实际存储的是 EndOffset 值
  - `script_serial_size` 实际存储的是 StartOffset 值
- parse_properties_from_export() 使用 `serial_offset + script_serial_offset` 计算属性数据起始位置，但这个值实际上是 EndOffset，不是 StartOffset

**影响:**
- 所有 UE 5.10+ 资产的属性数据偏移计算错误
- D-01 修复假设字段正确读取，但实际上字段语义颠倒

**建议修复:**
1. 交换读取顺序或重命名变量以匹配 UE 源码语义
2. 正确方案：
   ```python
   script_serial_start_offset = archive.read_i64()  # 第一个字段
   script_serial_end_offset = archive.read_i64()  # 第二个字段
   ```
3. parse_properties_from_export() 使用 `serial_offset + script_serial_start_offset`

**不在当前计划范围的原因:**
- 当前计划 (17-03) 专注于 D-03: PropertyTag Extensions 处理
- ObjectExport 序列化修复需要单独的计划和更广泛的测试验证
- 这是一个预先存在的 bug，不是当前任务引入的

**优先级:** HIGH - 需要在后续计划中修复

---

*记录时间: 2026-05-04*
*Phase: 17-property-parsing-fix*