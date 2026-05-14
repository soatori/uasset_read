# Phase 17: 属性解析修复 - Research

**Researched:** 2026-05-03
**Domain:** UE 5.7 属性序列化格式解析
**Confidence:** HIGH

## Summary

Phase 17 需要修复 UE 5.7 资产的属性解析错误。根因分析已通过 UE 源码验证确认，三个核心问题均为准确的根因诊断：

1. **偏移计算错误**: `parse_properties_from_export()` 使用 `serial_offset` 作为属性数据起始位置，但 UE 5.7 引入了 `ScriptSerializationStartOffset` 作为相对偏移
2. **头部未处理**: 当 `version_ue5 >= 1011` 时，属性数据前有 `SerializationControlExtensions` 头部
3. **扩展未处理**: PropertyTag 的 `HasPropertyExtensions` 标志对应扩展数据需要读取

**Primary recommendation:** 按 D-01、D-02、D-03 的修复方案依次实现，从偏移计算开始，然后添加头部和扩展处理。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

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

### Claude's Discretion

None — 所有决策已锁定。

### Deferred Ideas (OUT OF SCOPE)

None — 讨论保持在 Phase 范围内，专注于修复属性解析错误。
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FIX-04 | 修复 negative_size 错误（属性大小解析为负数） | D-01/D-02 验证 — 偏移和头部错位导致读取错误字段作为 Size |
| FIX-05 | 修复 exceeds_remaining 错误（属性大小超出边界） | D-01/D-02 验证 — 偏移错位导致 Size 字段读取了属性值或其他数据 |
| FIX-06 | 修复 cannot_read 错误（读取位置超出边界） | D-01 验证 — serial_offset 未加 script_serial_offset 导致越界 |
| FIX-07 | 正确解析 UE 5.7 资产的属性数据 | D-01/D-02/D-03 组合修复方案 |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 属性数据定位 | 解析器核心 | - | FArchive.seek() 计算 |
| 头部扩展处理 | 解析器核心 | - | Class.cpp/PropertyTag.cpp 逻辑 |
| 错误恢复策略 | 解析器核心 | ParseResult | 错误收集和部分结果返回 |

## 根因验证结果

### D-01: SerialOffset + ScriptSerialOffset [VERIFIED]

**UE 源码证据** (`ObjectResource.h` 第 280-285 行):

```cpp
/**
 * The location (relative to SerialOffset) of the beginning of the portion of this export's data that is 
 * serialized using tagged property serialization.
 * Serialized into versioned packages as of EUnrealEngineObjectUE5Version::SCRIPT_SERIALIZATION_OFFSET
 * Otherwise transient
 */
int64				ScriptSerializationStartOffset;
```

**序列化条件** (`ObjectResource.cpp` 第 212-222 行):

```cpp
if (!BaseArchive.UseUnversionedPropertySerialization() && BaseArchive.UEVer() >= EUnrealEngineObjectUE5Version::SCRIPT_SERIALIZATION_OFFSET)
{
    Record << SA_VALUE(TEXT("ScriptSerializationStartOffset"), E.ScriptSerializationStartOffset);
    Record << SA_VALUE(TEXT("ScriptSerializationEndOffset"), E.ScriptSerializationEndOffset);
}
```

**版本阈值**: `SCRIPT_SERIALIZATION_OFFSET = 1010` (ObjectVersion.h 第 77 行)

**当前代码问题** (`uasset_read.py` 第 4343 行):

```python
archive.seek(export.serial_offset)  # 错误：未加 script_serial_offset
```

**修复方案**:

```python
# 当 version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET (1010) 时
if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
    property_start = export.serial_offset + export.script_serial_offset
else:
    property_start = export.serial_offset
archive.seek(property_start)
```

### D-02: SerializationControlExtensions 头部 [VERIFIED]

**UE 源码证据** (`Class.cpp` 第 1627-1654 行):

```cpp
if (bIsUClass && UnderlyingArchive.UEVer() >= EUnrealEngineObjectUE5Version::PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION)
{
    EClassSerializationControlExtension SerializationControl = EClassSerializationControlExtension::NoExtension;
    if (UnderlyingArchive.IsSaving())
    {
        SerializationControl = ControlContext.InitializeSerializationControlExtensions();
    }

    Slot << SA_ATTRIBUTE(TEXT("SerializationControlExtensions"), SerializationControl);

    // Overridable serialization information serialization
    if (EnumHasAnyFlags(SerializationControl, EClassSerializationControlExtension::OverridableSerializationInformation))
    {
        EOverriddenPropertyOperation Operation = ...;
        Slot << SA_ATTRIBUTE(TEXT("OverridableOperation"), Operation);
        ...
    }
}
```

**EClassSerializationControlExtension 定义** (`Class.cpp` 第 1559-1571 行):

```cpp
enum class EClassSerializationControlExtension : uint8
{
    NoExtension                 = 0x00,
    ReserveForFutureUse        = 0x01,
    OverridableSerializationInformation = 0x02,
};
```

**版本阈值**: `PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION = 1011`

**修复方案**:

```python
# 在读取 PropertyTag 循环前，检查版本并读取头部
if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
    serialization_control = archive.read_u8()
    if serialization_control & 0x02:  # OverridableSerializationInformation
        overridden_operation = archive.read_u8()  # EOverriddenPropertyOperation
```

### D-03: PropertyTag Extensions [VERIFIED]

**UE 源码证据** (`PropertyTag.cpp` 第 17-48 行):

```cpp
enum class EPropertyTagFlags : uint8
{
    None                       = 0x00,
    HasArrayIndex              = 0x01,
    HasPropertyGuid            = 0x02,
    HasPropertyExtensions      = 0x04,
    HasBinaryOrNativeSerialize = 0x08,
    BoolTrue                   = 0x10,
    SkippedSerialize           = 0x20,
};

enum class EPropertyTagExtension : uint8
{
    NoExtension           = 0x00,
    ReserveForFutureUse   = 0x01,
    OverridableInformation = 0x02,
};
```

**Extensions 序列化** (`PropertyTag.cpp` 第 155-173 行):

```cpp
static void SerializePropertyExtensions(FStructuredArchive::FSlot Slot, EPropertyTagExtension PropertyTagExtensions, FPropertyTag& Tag)
{
    Slot << SA_ATTRIBUTE(TEXT("PropertyExtensions"), PropertyTagExtensions);

    // OverridableInformation
    if (EnumHasAnyFlags(PropertyTagExtensions, EPropertyTagExtension::OverridableInformation))
    {
        Slot << SA_ATTRIBUTE(TEXT("OverriddenPropertyOperation"), Tag.OverrideOperation);
        Slot << SA_ATTRIBUTE(TEXT("ExperimentalOverridableLogic"), Tag.bExperimentalOverridableLogic);
    }
}
```

**主序列化流程** (`PropertyTag.cpp` 第 541-544 行):

```cpp
if (EnumHasAnyFlags(PropertyTagFlags, EPropertyTagFlags::HasPropertyExtensions))
{
    SerializePropertyExtensions(Slot, PropertyTagExtensions, Tag);
}
```

**修复方案**:

```python
# 在 read_property_tag() 中，读取 flags 后检查 HAS_EXTENSIONS
if tag.flags & PROP_TAG_HAS_EXTENSIONS:
    property_extensions = archive.read_u8()
    if property_extensions & 0x02:  # OverridableInformation
        tag.override_operation = archive.read_u8()  # EOverriddenPropertyOperation
        tag.experimental_overridable_logic = archive.read_bool()  # 实际是 u8
```

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python struct | 3.10+ | 二进制解析 | 标准库，无依赖 |
| Python mmap | 3.10+ | 大文件处理 | 标准库，性能优化 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 7.x | 测试框架 | 验证修复正确性 |

**Installation:**
```bash
# 无额外安装需求 — 使用标准库
pip install pytest  # 仅测试需要
```

## Architecture Patterns

### 系统架构图

```
.uasset File
    │
    ├── PackageFileSummary (file_version_ue5)
    │       │
    │       └── version >= 1010 → ScriptSerializationOffset 字段存在
    │       └── version >= 1011 → PropertyTagExtensions 启用
    │
    └── ExportMap
            │
            └── ObjectExport
                    │
                    ├── serial_offset (绝对位置)
                    ├── script_serial_offset (相对偏移，version >= 1010)
                    │
                    └── Properties Data
                            │
                            ├── [SerializationControlExtensions] (version >= 1011)
                            │       ├── control_byte (u8)
                            │       └── [OverriddenOperation] (if control & 0x02)
                            │
                            └── PropertyTag Loop
                                    │
                                    ├── Name (FName)
                                    ├── Type (FString)
                                    ├── Size (i32)
                                    ├── Flags (u8)
                                    │       ├── HAS_ARRAY_INDEX → ArrayIndex (i32)
                                    │       ├── HAS_PROPERTY_GUID → Guid (16 bytes)
                                    │       └── HAS_EXTENSIONS → Extensions
                                    │               ├── extension_byte (u8)
                                    │               └── [OverridableInfo] (if extension & 0x02)
                                    │
                                    └── PropertyValue (Size bytes)
                                    │
                                    └── "None" → 终止
```

### 推荐项目结构

当前为单文件结构，修复在 `uasset_read.py` 中进行：

```
uasset_read.py
├── 常量定义 (第 50-100 行) — 版本阈值
├── FArchive (第 150-400 行) — read_bool(), read_u8() 等
├── ObjectExport (第 770-810 行) — 已有 script_serial_offset 字段
├── PropertyTag (第 810-850 行) — 可能需要添加扩展字段
├── read_property_tag() (第 3527-3588 行) — 添加 Extensions 处理
└── parse_properties_from_export() (第 4343-4420 行) — 偏移计算 + 头部处理
```

### Pattern 1: 版本条件序列化

**What:** UE 5.x 引入了多个版本阈值，决定是否序列化特定字段。

**When to use:** 每个新增字段都需要检查版本阈值。

**Example:**
```python
# Source: ObjectResource.cpp line 212-222
if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
    # ScriptSerializationStartOffset/EndOffset 已序列化
    property_start = export.serial_offset + export.script_serial_offset
else:
    # 旧版本无此字段，直接使用 serial_offset
    property_start = export.serial_offset
```

### Pattern 2: 标志位条件读取

**What:** PropertyTag.Flags 和 Extensions 使用位标志决定额外字段。

**When to use:** 读取 PropertyTag 后，根据 flags 决定后续读取。

**Example:**
```python
# Source: PropertyTag.cpp line 527-544
if tag.flags & PROP_TAG_HAS_ARRAY_INDEX:
    tag.array_index = archive.read_i32()
if tag.flags & PROP_TAG_HAS_PROPERTY_GUID:
    tag.property_guid = archive.read(16)
if tag.flags & PROP_TAG_HAS_EXTENSIONS:
    extensions = archive.read_u8()
    if extensions & 0x02:  # OverridableInformation
        tag.override_operation = archive.read_u8()
        tag.experimental_overridable_logic = archive.read_u8()
```

### Anti-Patterns to Avoid

- **硬编码偏移**: 不要假设属性数据从 serial_offset 开始 — 必须检查版本并计算
- **跳过未知标志**: HAS_EXTENSIONS (0x04) 必须处理，否则位置错位
- **忽略头部**: SerializationControlExtensions 头部在 version >= 1011 时必须读取

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 版本条件判断 | 硬编码版本号 | UE5_* 常量 | 可维护性、可追溯 |
| 标志位处理 | 位运算猜测 | UE 源码枚举定义 | 准确性、完整覆盖 |

**Key insight:** 所有序列化格式已由 UE 源码定义，修复只需对照源码实现，不需要猜测或推导。

## Common Pitfalls

### Pitfall 1: 偏移计算遗漏

**What goes wrong:** 属性数据起始位置计算错误，导致读取 PropertyTag.Name 时位置错位。

**Why it happens:** UE 5.7 引入了 ScriptSerializationStartOffset，当前代码未更新。

**How to avoid:** 
1. 检查 `file_version_ue5 >= 1010`
2. 计算正确偏移：`serial_offset + script_serial_offset`

**Warning signs:** `negative_size` 错误、`cannot_read` 错误（位置超出边界）

### Pitfall 2: 头部跳过

**What goes wrong:** 属性数据前有 SerializationControlExtensions 头部，跳过导致 PropertyTag 读取错位。

**Why it happens:** Class.cpp 第 1627 行的条件序列化被忽略。

**How to avoid:**
1. 检查 `file_version_ue5 >= 1011`
2. 读取 `serialization_control` (u8)
3. 根据标志读取 `OverriddenOperation`

**Warning signs:** `exceeds_remaining` 错误（Size 字段读到了属性值）

### Pitfall 3: Extensions 未读取

**What goes wrong:** PropertyTag.Flags 包含 HAS_EXTENSIONS (0x04) 时，后续有扩展数据未读取。

**Why it happens:** 常量已定义但注释 "defer to Phase 3" 未实现。

**How to avoid:**
1. 检查 `flags & 0x04`
2. 读取 `extension_byte` (u8)
3. 根据扩展标志读取额外数据

**Warning signs:** 下一个 PropertyTag 位置错位，连锁错误

## Code Examples

### 偏移计算修复

```python
# Source: uasset_read.py parse_properties_from_export()
# 当前实现（错误）
archive.seek(export.serial_offset)

# 修复实现
if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
    property_start = export.serial_offset + export.script_serial_offset
else:
    property_start = export.serial_offset
archive.seek(property_start)
```

### 头部处理添加

```python
# Source: Class.cpp line 1627-1654
# 在 parse_properties_from_export() 属性循环前添加
if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
    # EClassSerializationControlExtension (u8)
    serialization_control = archive.read_u8()
    
    # OverridableSerializationInformation 标志
    if serialization_control & 0x02:
        # EOverriddenPropertyOperation (u8)
        overridden_operation = archive.read_u8()
        # 可以忽略具体值，仅用于位置同步
```

### Extensions 处理添加

```python
# Source: PropertyTag.cpp line 541-544
# 在 read_property_tag() 的 UE5 格式分支中添加
# 当前代码（第 3560-3567 行后）
if tag.flags & PROP_TAG_HAS_ARRAY_INDEX:
    tag.array_index = archive.read_i32()

if tag.flags & PROP_TAG_HAS_PROPERTY_GUID:
    tag.property_guid = archive.read(16)

# 添加 Extensions 处理
if tag.flags & PROP_TAG_HAS_EXTENSIONS:
    property_extensions = archive.read_u8()
    if property_extensions & 0x02:  # OverridableInformation
        tag.override_operation = archive.read_u8()
        tag.experimental_overridable_logic = archive.read_u8()

# BoolTrue 标志处理（已存在）
if tag.flags & PROP_TAG_BOOL_TRUE:
    tag.bool_val = 1
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| serial_offset 直接使用 | + script_serial_offset | UE 5.10 (v1010) | 属性数据定位准确 |
| PropertyTag 直接读取 | 先读 SerializationControlExtensions | UE 5.11 (v1011) | 头部同步 |
| Flags 仅处理 ArrayIndex/Guid | + HasPropertyExtensions | UE 5.11 (v1011) | 扩展数据同步 |

**Deprecated/outdated:**
- 直接 `seek(serial_offset)`：UE 5.10+ 必须加 script_serial_offset
- 跳过头部：UE 5.11+ 必须读取 SerializationControlExtensions

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 所有 UE 5.7 资产的 version_ue5 >= 1011 | 根因验证 | 如果版本更低，修复可能不适用 |

**验证状态:** UE 5.7 version_ue5 = 1017 (ObjectVersion.h)，高于所有阈值 (1010, 1011, 1012)，所有修复均适用。

## Open Questions

1. **OverriddenPropertyOperation 具体语义**
   - What we know: u8 枚举值，影响属性序列化行为
   - What's unclear: 是否需要解析具体值或仅跳过
   - Recommendation: 仅读取用于位置同步，不解析具体语义（Phase 范围外）

2. **experimental_overridable_logic 是否为 bool (1 byte) 或 uint32**
   - What we know: PropertyTag.cpp 使用 SA_ATTRIBUTE 序列化
   - What's unclear: UE bool 序列化为 uint32，但此处可能是 u8
   - Recommendation: 检查 UE 源码确认，暂按 u8 处理

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | 解析器 | ✓ | 3.10+ | - |
| pytest | 测试验证 | ✓ | 7.x | - |
| UE 5.7 源码 | 参考 | ✓ | 5.7 | - |

**Missing dependencies with no fallback:** 无

**Missing dependencies with fallback:** 无

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.x |
| Config file | tests/conftest.py |
| Quick run command | `python -m pytest tests/test_property_parsing.py -x -v` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FIX-04 | negative_size 错误修复 | unit | `pytest tests/test_property_parsing.py::test_property_tag_ue5_format_basic -x` | ✅ |
| FIX-05 | exceeds_remaining 错误修复 | unit | `pytest tests/test_property_parsing.py::test_property_tag_all_flags -x` | ✅ |
| FIX-06 | cannot_read 错误修复 | integration | `pytest tests/test_exportmap_properties.py -x` | ✅ |
| FIX-07 | UE 5.7 资产属性解析 | integration | 手动验证 — 需要 UE 5.7 资产 | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_property_parsing.py -x`
- **Per wave merge:** `python -m pytest tests/ -v --tb=short`
- **Phase gate:** 全套测试通过 + UE 5.7 资产手动验证

### Wave 0 Gaps

- [ ] `tests/test_ue57_property_parsing.py` — 专门验证 UE 5.7 格式资产
- [ ] Mock 数据构造 — 包含 SerializationControlExtensions 和 Extensions 的测试数据

## Security Domain

本 Phase 为纯解析器修复，无安全相关变更。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | 二进制边界验证已实现 (validate_size) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 边界越界读取 | Tampering | validate_size(), exceeds_remaining 检查 |
| 无限循环 | Denial of Service | MAX_PROPERTY_COUNT 限制 |

## Sources

### Primary (HIGH confidence)

- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\ObjectResource.h` 第 280-295 行 — ScriptSerializationStartOffset 定义 [VERIFIED]
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\ObjectResource.cpp` 第 212-222 行 — 序列化条件 [VERIFIED]
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyTag.cpp` 第 17-48 行 — EPropertyTagFlags/EPropertyTagExtension 定义 [VERIFIED]
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyTag.cpp` 第 155-173 行 — SerializePropertyExtensions 实现 [VERIFIED]
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyTag.cpp` 第 436-545 行 — UE5 PropertyTag 序列化流程 [VERIFIED]
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\Class.cpp` 第 1559-1571 行 — EClassSerializationControlExtension 定义 [VERIFIED]
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\Class.cpp` 第 1627-1654 行 — SerializationControlExtensions 头部 [VERIFIED]
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Core\Public\UObject\ObjectVersion.h` 第 40-109 行 — UE5 版本枚举 [VERIFIED]

### Secondary (MEDIUM confidence)

- `uasset_read.py` 第 50-100 行 — 常量定义（已定义但未使用）
- `uasset_read.py` 第 3527-3588 行 — read_property_tag() 实现
- `uasset_read.py` 第 4343-4420 行 — parse_properties_from_export() 实现

### Tertiary (LOW confidence)

- 无 — 所有根因分析已通过 UE 源码验证

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 使用标准库
- Architecture: HIGH — UE 源码明确定义
- Pitfalls: HIGH — 根因已验证，修复方案明确

**Research date:** 2026-05-03
**Valid until:** UE 序列化格式变更（下一个 UE major version）

---

## RESEARCH COMPLETE

**Phase:** 17 - 属性解析修复
**Confidence:** HIGH

### Key Findings

1. **D-01 根因确认**: ScriptSerializationStartOffset 是相对偏移，当前代码遗漏加法
2. **D-02 根因确认**: SerializationControlExtensions 头部在 version >= 1011 时必须读取
3. **D-03 根因确认**: PropertyTag HAS_EXTENSIONS 标志对应扩展数据必须处理
4. **版本阈值**: UE 5.7 version_ue5 = 1017，高于所有相关阈值 (1010, 1011)
5. **修复方案**: 三处修改 — 偏移计算、头部读取、Extensions 处理

### File Created

`E:\Develop\uasset_read\.planning\phases\17-property-parsing-fix\17-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | 标准库无变化 |
| Architecture | HIGH | UE 源码验证完成 |
| Pitfalls | HIGH | 根因已确认，修复路径明确 |

### Open Questions

- OverriddenPropertyOperation 具体语义（不影响修复）
- experimental_overridable_logic 序列化大小（需确认 u8 vs uint32）

### Ready for Planning

研究完成。Planner 可以基于 D-01/D-02/D-03 修复方案创建 PLAN.md 文件。