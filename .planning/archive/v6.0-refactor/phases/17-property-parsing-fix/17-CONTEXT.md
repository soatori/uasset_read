# Phase 17: 属性解析修复 - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

解决 UE 5.7 资产的属性解析错误，使 69 个导出对象的属性可以正确解析。当前 53/69 (76.8%) 导出对象有属性解析错误，错误类型包括 negative_size (2)、exceeds_remaining (9)、cannot_read (42)。

**范围锚点：** 仅修复属性解析错误，不添加新属性类型支持或功能扩展。

</domain>

<decisions>
## Implementation Decisions

### 根因分析（已验证 UE 源码）

**D-01: SerialOffset + ScriptSerialOffset 偏移计算错误**

当前代码 `parse_properties_from_export()` 使用：
```python
archive.seek(export.serial_offset)  # 错误
```

UE 源码 `ObjectResource.h` 第 280-285 行明确注释：
- `ScriptSerializationStartOffset` 是 "relative to SerialOffset" 的偏移

正确实现应为：
```python
archive.seek(export.serial_offset + export.script_serial_offset)
```

**D-02: SerializationControlExtensions 头部未处理**

UE 源码 `Class.cpp` 第 1627-1654 行，当 UE5 >= 1011 (PROPERTY_TAG_EXTENSION) 时，属性数据起始位置有额外头部：
- `EClassSerializationControlExtension` (1 byte) — 控制扩展标志
- 条件字段：`OverriddenPropertyOperation`（如果标志包含 OverridableSerializationInformation）

当前代码直接读取 PropertyTag，跳过了这个头部，导致位置错位。

**D-03: PropertyTag Extensions 未处理**

UE 源码 `PropertyTag.cpp` 第 541-544 行，当 flags & PROP_TAG_HAS_EXTENSIONS (0x04) 时：
- 需要读取 `EPropertyTagExtension` (1 byte)
- 条件读取 `OverridableInformation` 扩展数据

代码已定义常量 `PROP_TAG_HAS_EXTENSIONS = 0x04` (第52行)，但注释 "defer to Phase 3" 未实现。

### 错误处理策略

**D-04: 分层错误处理策略**

| 层级 | 策略 | 触发条件 |
|------|------|----------|
| 1 | 尝试恢复 | PropertyTag.Size 有效，根据 Size 跳到预期位置 |
| 2 | 跳过属性 | 恢复失败但 Size 可用，跳过并记录警告 |
| 3 | 中断解析 | Size 无效或严重错误，中断当前导出的属性解析 |

### 未知属性类型处理

**D-05: 存储原始数据**

遇到无法识别的属性类型时：
- 读取 Size 字节的原始数据
- 存储为 `PropertyValue(type="Unknown_<TypeName>", value=<raw_bytes>)`
- 继续解析下一个属性

</decisions>

<specifics>
## Specific Ideas

**UE 源码关键文件定位：**
- `PropertyTag.cpp` 第 436-545 行 — UE5 新格式属性标签序列化
- `Class.cpp` 第 1615-1714 行 — SerializeVersionedTaggedProperties 流程
- `ObjectResource.h` 第 226-295 行 — FObjectExport 结构定义
- `ObjectResource.cpp` 第 212-222 行 — ScriptSerializationOffset 序列化条件

**版本阈值验证：**
- UE5_PROPERTY_TAG_EXTENSION = 1011 — SerializationControlExtensions 头部启用
- UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012 — 完整 TypeName 格式启用
- UE5_SCRIPT_SERIALIZATION_OFFSET = 1010 — ScriptSerialOffset 字段启用
- UE 5.7 version_ue5 = 1017 — 全部启用

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### UE 5.7 源码参考（只读）

- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyTag.cpp` — 属性标签序列化格式（第 436-545 行 UE5 新格式，第 16-48 行 EPropertyTagFlags/EPropertyTagExtension 定义）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\Class.cpp` — SerializeVersionedTaggedProperties（第 1615-1714 行），SerializationControlExtensions 头部（第 1627-1654 行）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\ObjectResource.h` — FObjectExport 结构（第 226-295 行），ScriptSerializationStartOffset 注释（第 280-285 行）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\ObjectResource.cpp` — Export 序列化（第 165-225 行），ScriptSerializationOffset 条件（第 212-222 行）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Core\Public\UObject\ObjectVersion.h` — EUnrealEngineObjectUE5Version 枚举（第 40-109 行），版本阈值定义

### 项目文档

- `.planning/phases/16-bool-serialization-fix/16-CONTEXT.md` — Phase 16 修复 Bool 序列化的上下文，serial_offset 验证数据
- `.planning/phases/17-property-parsing-fix/17-PLAN.md` — 问题摘要和错误示例
- `.planning/ROADMAP.md` — Phase 17 目标和 Success Criteria（第 219-236 行）

</canonical_refs>

<code_context>
## Existing Code Insights

### 需要修改的位置

1. **`parse_properties_from_export()` (第 4343 行)**
   - 当前：`archive.seek(export.serial_offset)`
   - 修正：计算正确偏移 + 读取 SerializationControlExtensions 头部

2. **`read_property_tag()` (第 3527-3588 行)**
   - 当前：仅处理 HAS_ARRAY_INDEX 和 HAS_PROPERTY_GUID
   - 修正：添加 HAS_EXTENSIONS (0x04) 处理

3. **`ObjectExport` dataclass (第 780-807 行)**
   - 已有 `script_serial_offset` 字段，需正确使用

### 已定义但未使用的常量

- `PROP_TAG_HAS_EXTENSIONS = 0x04` (第 52 行) — 需实现
- `PROP_TAG_HAS_BINARY_OR_NATIVE = 0x08` (第 53 行) — 可能需要
- `PROP_TAG_SKIPPED_SERIALIZE = 0x20` (第 55 行) — 可能需要
- `UE5_PROPERTY_TAG_EXTENSION = 1011` (第 80 行) — 用于条件判断

### Integration Points

- 属性解析入口：`parse_uasset()` 第 4530-4539 行调用 `parse_properties_from_export()`
- 错误收集：`ParseResult.errors` 列表存储解析错误
- 输出格式：PropertyValue 列表用于 JSON 输出

</code_context>

<deferred>
## Deferred Ideas

None — 讨论保持在 Phase 范围内，专注于修复属性解析错误。

</deferred>

---
*Phase: 17-property-parsing-fix*
*Context gathered: 2026-05-03*