# FPropertyTag 属性标签

> **UE 源码对照**: `Runtime/CoreUObject/Public/UObject/PropertyTag.h`, `Runtime/CoreUObject/Private/UObject/PropertyTag.cpp`
> **最后对齐**: UE 5.7 (2026-06)

## 概述

FPropertyTag 是 UObject 属性序列化（`SerializeTaggedProperties`）的元数据结构。每个被序列化的属性前都会写入一个 FPropertyTag，描述属性名称、类型、数据大小、GUID 等元信息。属性数据随后紧跟写入。属性列表以 `Name == NAME_None` 的终止 tag 结束。

---

## 完整字段表

### 结构体定义（UE 5.7）

```cpp
// PropertyTag.h L37-68
struct FPropertyTag
{
    UE::FPropertyTypeName TypeName;        // 完整类型名（含参数，UE5.5+）
    FName Type;                            // 属性类型（StructProperty/IntProperty 等）
    FName Name;                            // 属性名称（NAME_None 为终止标记）
    int32 Size = 0;                        // 属性数据字节数（保存后回填）
    int32 ArrayIndex = INDEX_NONE;         // 数组元素索引（0 = 非数组）
    int64 SizeOffset = INDEX_NONE;         // Size 字段在流中的偏移（保存时使用）
    FGuid StructGuid;                      // 结构体类型 GUID（已废弃，合入 TypeName）
    FGuid PropertyGuid;                    // 属性 GUID（蓝图重命名属性匹配用）
    uint8 HasPropertyGuid = 0;             // 是否有 PropertyGuid
    uint8 BoolVal = 0;                     // BoolProperty 的值（不序列化数据）
    EPropertyTagSerializeType SerializeType;  // 序列化方式标记
    EOverriddenPropertyOperation OverrideOperation;  // 可覆盖序列化状态
    bool bExperimentalOverridableLogic = false;      // CPF_ExperimentalOverridableLogic 标记
};
```

### 序列化标志（EPropertyTagFlags）

```cpp
// PropertyTag.cpp L17-26
enum class EPropertyTagFlags : uint8
{
    None                        = 0x00,
    HasArrayIndex               = 0x01,   // ArrayIndex != 0 时设置
    HasPropertyGuid             = 0x02,   // 存在 PropertyGuid
    HasPropertyExtensions       = 0x04,   // 存在扩展字节
    HasBinaryOrNativeSerialize  = 0x08,   // 使用二进制或原生序列化
    BoolTrue                    = 0x10,   // BoolProperty 值为 true
    SkippedSerialize            = 0x20,   // 序列化被跳过
};
```

### 序列化扩展（EPropertyTagExtension）

```cpp
// PropertyTag.cpp L34-46
enum class EPropertyTagExtension : uint8
{
    NoExtension                = 0x00,
    ReserveForFutureUse        = 0x01,   // 预留扩展位
    OverridableInformation     = 0x02,   // 可覆盖序列化信息
};
```

---

## 二进制序列化格式

### 序列化顺序（UE5.5+，完整类型名格式）

```
┌─────────────────────────────────────────────────────────┐
│ Name (FName)                                             │
│   → NAME_None 时终止，不继续读取                          │
├─────────────────────────────────────────────────────────┤
│ TypeName (FName)                                         │
│   → 完整类型路径，如 "StructProperty(Vector)"             │
├─────────────────────────────────────────────────────────┤
│ Size (int32)                                             │
│   → 保存时先写 0，属性数据写完后回填                       │
├─────────────────────────────────────────────────────────┤
│ Flags (uint8)                                            │
│   → EPropertyTagFlags 组合                               │
├─────────────────────────────────────────────────────────┤
│ [ArrayIndex (int32)]                                     │
│   → 仅当 Flags & HasArrayIndex (0x01)                    │
├─────────────────────────────────────────────────────────┤
│ [PropertyGuid (FGuid, 16 bytes)]                         │
│   → 仅当 Flags & HasPropertyGuid (0x02)                  │
├─────────────────────────────────────────────────────────┤
│ [PropertyExtensions (uint8)]                             │
│   → 仅当 Flags & HasPropertyExtensions (0x04)            │
│   → 若含 OverridableInformation (0x02):                  │
│       OverrideOperation (uint8)                          │
│       bExperimentalOverridableLogic (uint8)              │
├─────────────────────────────────────────────────────────┤
│ Property Data (Size bytes)                               │
│   → BoolProperty: 不写入（值在 Flags.BoolTrue 中）       │
│   → 其他类型: 调用 Property->SerializeItem()             │
└─────────────────────────────────────────────────────────┘
│ Name (FName) → 下一个属性或 NAME_None 终止               │
```

### Flags 各标志位含义

| 位 | 标志 | 说明 | 附加数据 |
|----|------|------|----------|
| 0x01 | HasArrayIndex | ArrayIndex 非零 | 追加 `int32 ArrayIndex` |
| 0x02 | HasPropertyGuid | 存在属性 GUID | 追加 `FGuid PropertyGuid` |
| 0x04 | HasPropertyExtensions | 存在序列化扩展 | 追加扩展字节（见下） |
| 0x08 | HasBinaryOrNativeSerialize | 使用二进制/原生序列化 | 无附加数据 |
| 0x10 | BoolTrue | BoolProperty 值为 true | 无附加数据（值在 tag 中） |
| 0x20 | SkippedSerialize | 属性序列化被跳过 | 无附加数据，Size 通常为 0 |

### PropertyExtensions 格式

当 `Flags & 0x04` 时写入：

```
PropertyExtensions (uint8)
  → 0x01: ReserveForFutureUse（预留）
  → 0x02: OverridableInformation
      → 追加 OverrideOperation (uint8)
      → 追加 bExperimentalOverridableLogic (uint8)
```

---

## BoolProperty 特殊处理

**BoolProperty 是唯一不写入属性数据的类型**。布尔值直接编码在 `Flags.BoolTrue` (0x10) 中：

```cpp
// PropertyTag.cpp L509-512 (Saving)
if (Tag.BoolVal && Tag.Type == NAME_BoolProperty)
{
    PropertyTagFlags |= EPropertyTagFlags::BoolTrue;
}

// PropertyTag.cpp L524 (Loading)
Tag.BoolVal = EnumHasAnyFlags(PropertyTagFlags, EPropertyTagFlags::BoolTrue);
```

**序列化行为**：
- 写入 tag 时，`BoolVal` 编码到 `Flags` 中，不写额外数据字节
- `SerializeTaggedProperty` 中对 BoolProperty 调用 `UnderlyingArchive.Serialize(nullptr, 0)` — 空操作
- 读取时从 `Flags` 中提取 `BoolTrue` 位，直接赋值

**影响**：解析器对 BoolProperty 不需要 seek 过 Size 字节（Size 通常为 0）。

---

## 版本相关字段

| 版本门控 | 字段 | 说明 |
|----------|------|------|
| UE4 所有版本 | Name, Type, Size | 基础字段始终存在 |
| UE4 < 5.5 (PROPERTY_TAG_COMPLETE_TYPE_NAME) | 旧格式: StructName, EnumName, InnerType, ValueType 分别序列化 | 见下文旧格式 |
| UE4 >= VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG (336) | StructGuid | StructProperty 的类型 GUID |
| UE4 >= VAR_UE4_ARRAY_PROPERTY_INNER_TAGS (228) | InnerType (ArrayProperty) | 数组内元素类型 |
| UE4 >= VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT (322) | InnerType/ValueType (Set/Map) | 集合/映射类型信息 |
| UE4 >= VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG (365) | HasPropertyGuid + PropertyGuid | 属性 GUID（蓝图重命名） |
| UE5 >= PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION | PropertyExtensions | 序列化扩展字节 |
| UE5.5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME (1012) | 新格式: TypeName 包含完整类型路径 | 替代旧版分散字段 |

---

## 旧格式（UE4 / UE5 < 5.5）

旧版本不使用 `TypeName` 完整路径，而是根据 `Type` 分别序列化参数：

| Type 值 | 附加序列化字段 |
|---------|---------------|
| StructProperty | StructName (FName) + [StructGuid (FGuid)] |
| BoolProperty | BoolVal (uint8) — 注意：旧版 BoolVal 是单独字段 |
| ByteProperty | EnumName (FName) |
| EnumProperty | EnumName (FName) |
| ArrayProperty | [InnerType (FName)]（需 >= VAR_UE4_ARRAY_PROPERTY_INNER_TAGS） |
| OptionalProperty | InnerType (FName) |
| SetProperty | InnerType (FName)（需 >= VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT） |
| MapProperty | InnerType (FName) + ValueType (FName)（需 >= VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT） |

---

## 属性终止条件

属性列表以 `Name == NAME_None` 的 tag 结束：

```cpp
// PropertyTag.cpp L464-468
Slot << SA_ATTRIBUTE(TEXT("Name"), Tag.Name);
if (Tag.Name.IsNone())
{
    return;  // 终止，不读取后续字段
}
```

**解析规则**：
1. 读取 Name（FName）
2. 若 Name 为 NAME_None，终止属性循环
3. 否则继续读取 Type、Size 等字段

---

## EPropertyTagSerializeType 枚举

```cpp
enum class EPropertyTagSerializeType : uint8
{
    Unknown,        // 从旧版本加载或尚未保存
    Skipped,        // 属性值序列化被跳过（tag 无数据）
    Property,       // 使用 tagged property 序列化
    BinaryOrNative, // 使用二进制或原生序列化
};
```

- `Skipped`: Flags 包含 0x20，表示属性被跳过（Size 通常为 0）
- `BinaryOrNative`: Flags 包含 0x08，表示使用非 tagged 序列化路径
- `Property`: 默认，正常 tagged 序列化

---

## Size 回填机制

```cpp
// PropertyTag.cpp L478-482
if (UnderlyingArchive.IsSaving())
{
    Tag.SizeOffset = UnderlyingArchive.Tell();  // 记录 Size 字段位置
}
Slot << SA_ATTRIBUTE(TEXT("Size"), Tag.Size);   // 先写 0

// ... 属性数据序列化 ...

// UStruct::SerializeTaggedProperties 中回填:
// Ar.Seek(TagSizeOffset); Ar << SerializedSize; Ar.Seek(EndOffset);
```

**流程**：
1. 写入 Size = 0（占位）
2. 序列化属性数据
3. 计算实际字节数
4. 回 seek 到 Size 位置写入实际值
5. seek 回属性数据末尾继续

---

## 与解析器的对应关系

| UE 字段 | 解析器位置 | 说明 |
|---------|-----------|------|
| Name | `read_property_tag()` → `tag.name` | 属性名 |
| Type | `read_property_tag()` → `tag.type` | 类型名 |
| Size | `read_property_tag()` → `tag.size` | 数据大小 |
| Flags | `read_property_tag()` → `tag.flags` | 标志位 |
| ArrayIndex | `read_property_tag()` → `tag.array_index` | 数组索引 |
| StructGuid | `parse_struct_property()` | 结构体 GUID |
| BoolVal | `parse_bool_property()` | 从 Flags.BoolTrue 提取 |
| PropertyGuid | `read_property_tag()` → `tag.property_guid` | 属性 GUID |
| PropertyExtensions | `read_property_tag()` | 扩展字节 |

---

## 源码引用

- `Runtime/CoreUObject/Public/UObject/PropertyTag.h` — FPropertyTag 结构定义
- `Runtime/CoreUObject/Private/UObject/PropertyTag.cpp` — 序列化实现、EPropertyTagFlags/EPropertyTagExtension
- `Runtime/CoreUObject/Private/UObject/Class.cpp` — `SerializeTaggedProperties` 入口
- `Runtime/Core/Public/UObject/ObjectVersion.h` — 版本门控常量
