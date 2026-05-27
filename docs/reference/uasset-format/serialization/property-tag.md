# FPropertyTag 属性标签

## 概述

FPropertyTag 是属性序列化的元数据结构，用于在 UObject 序列化过程中描述每个属性的名称、类型、大小等信息。每个属性在序列化时都会先写入一个 FPropertyTag，然后再写入实际的属性数据。

FPropertyTag 在加载流程中由 [LinkerLoad](linker-load.md) 的 Preload 阶段解析，在保存流程中由 [LinkerSave](linker-save.md) 构造并写入。属性标签序列化支持版本兼容，通过 UE4/UE5 双版本机制和 CustomVersion 机制处理不同版本的字段差异。

**核心职责：**
- 标记属性名称和类型
- 记录属性数据大小（用于跳过未知属性）
- 存储布尔属性值（BoolProperty 的值直接存储在 Tag 中）
- 提供容器类型的内部类型信息（Array/Set/Map/Optional）
- 支持蓝图属性重定向（通过 PropertyGuid）

## 字段表

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| Name | FName | 属性名称 | — |
| Type | FName | 属性类型名称（如 StructProperty） | — |
| TypeName | FPropertyTypeName | 完整类型名系统（包含类型参数） | UE5.4 新增，替代部分类型字段 |
| Size | int32 | 属性数据大小（字节） | — |
| ArrayIndex | int32 | 数组索引（非数组为 0） | — |
| SizeOffset | int64 | Size 字段在流中的序列化偏移 | 仅保存时记录，用于回写 Size |
| PropertyGuid | FGuid | 属性 GUID（支持蓝图重定向） | VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG |
| HasPropertyGuid | uint8 | 是否有 PropertyGuid | — |
| BoolVal | uint8 | 布尔值（仅 BoolProperty） | 值存储在 Tag 中，属性数据为空 |
| SerializeType | EPropertyTagSerializeType | 序列化类型标记 | UE5 新增，PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION |
| OverrideOperation | EOverriddenPropertyOperation | 重写操作标记 | UE5 新增 |
| bExperimentalOverridableLogic | bool | 实验性重写逻辑标记 | UE5 新增，CPF_ExperimentalOverridableLogic |
| Prop | FProperty* | 属性对象指针 | UE5.4 废弃，使用 GetProperty()/SetProperty() |
| StructName | FName | 结构体名称 | UE5.4 废弃，使用 GetType().GetParameterName(0) |
| StructGuid | FGuid | 结构体 GUID | UE5.4 废弃，使用 GetType().GetParameterName(1) |
| EnumName | FName | 枚举名称（ByteProperty/EnumProperty） | UE5.4 废弃，使用 GetType() |
| InnerType | FName | 内部类型（Array/Set/Optional） | UE5.4 废弃，使用 GetType() |
| ValueType | FName | 值类型（MapProperty 的 Value） | UE5.4 废弃，使用 GetType() |

**字段分组说明：**

- **核心字段：** Name, Type, Size — 所有版本必需
- **类型参数字段：** TypeName (UE5.4+) 或 StructName/EnumName/InnerType/ValueType (旧版本)
- **数组支持：** ArrayIndex — 数组元素的索引标记
- **蓝图重定向：** PropertyGuid, HasPropertyGuid — 支持属性重命名后仍能匹配
- **布尔优化：** BoolVal — 布尔值直接存储，无需额外数据
- **重写追踪：** SerializeType, OverrideOperation, bExperimentalOverridableLogic — UE5 新增，支持属性重写序列化

## 属性类型

### 数值类型

| 类型 | FName | 特殊处理 |
|------|-------|----------|
| ByteProperty | NAME_ByteProperty | 可有 EnumName（枚举字节） |
| IntProperty | NAME_IntProperty | 32 位整数 |
| Int64Property | NAME_Int64Property | 64 位整数 |
| FloatProperty | NAME_FloatProperty | 单精度浮点 |
| DoubleProperty | NAME_DoubleProperty | 双精度浮点 |

### 字符串类型

| 类型 | FName | 特殊处理 |
|------|-------|----------|
| StrProperty | NAME_StrProperty | FString 字符串 |
| NameProperty | NAME_NameProperty | FName 名称 |
| TextProperty | NAME_TextProperty | FText 本地化文本 |

### 容器类型

| 类型 | FName | 特殊处理 |
|------|-------|----------|
| ArrayProperty | NAME_ArrayProperty | InnerType（元素类型），VAR_UE4_ARRAY_PROPERTY_INNER_TAGS |
| MapProperty | NAME_MapProperty | InnerType + ValueType（Key/Value 类型） |
| SetProperty | NAME_SetProperty | InnerType（元素类型），VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT |
| OptionalProperty | NAME_OptionalProperty | InnerType（包装类型） |

### 引用类型

| 类型 | FName | 特殊处理 |
|------|-------|----------|
| ObjectProperty | NAME_ObjectProperty | UObject 硬引用 |
| SoftObjectProperty | NAME_SoftObjectProperty | TSoftObjectPtr 软引用 |
| WeakObjectProperty | NAME_WeakObjectProperty | TWeakObjectPtr 弱引用 |
| LazyObjectProperty | NAME_LazyObjectProperty | TLazyObjectPtr 惰性引用 |

### 特殊类型

| 类型 | FName | 特殊处理 |
|------|-------|----------|
| BoolProperty | NAME_BoolProperty | BoolVal 存储在 Tag 中，属性数据为空 |
| StructProperty | NAME_StructProperty | StructName + StructGuid，VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG |
| EnumProperty | NAME_EnumProperty | EnumName + ByteProperty（底层类型） |
| DelegateProperty | NAME_DelegateProperty | 单播委托 |
| MulticastDelegateProperty | NAME_MulticastDelegateProperty | 多播委托 |

**共计 20 种属性类型，覆盖所有常用属性。**

### EPropertyTagSerializeType 序列化类型

| 类型 | 值 | 说明 |
|------|-----|------|
| Unknown | 0 | 旧版本加载或未保存时使用 |
| Skipped | 1 | 跳过序列化（Tag 无属性值） |
| Property | 2 | 标签属性序列化（标准方式） |
| BinaryOrNative | 3 | 二进制/原生序列化（用于优化） |

**序列化类型判断：**
- SkippedSerialize 标志：SerializeType = Skipped
- HasBinaryOrNativeSerialize 标志：SerializeType = BinaryOrNative
- 默认：SerializeType = Property

### EOverriddenPropertyOperation 重写操作类型

| 类型 | 说明 |
|------|------|
| None | 无重写操作记录 |
| Modified | 某子属性有重写操作 |
| Replace | 从此属性向下全部重写 |
| Add | 容器中新增元素 |
| Remove | 容器中移除元素 |
| SubObjectsShadowing | 子对象阴影序列化（特殊用途） |

## 源码引用

### 结构定义

| 文件 | 内容 |
|------|------|
| `Runtime/CoreUObject/Public/UObject/PropertyTag.h` | FPropertyTag 结构定义、EPropertyTagSerializeType 枚举 |
| `Runtime/CoreUObject/Public/UObject/OverriddenPropertySet.h` | EOverriddenPropertyOperation 枚举定义 |
| `Runtime/CoreUObject/Public/UObject/PropertyTypeName.h` | FPropertyTypeName 类型名系统（UE5.4+） |

### 序列化实现

| 文件 | 内容 |
|------|------|
| `Runtime/CoreUObject/Private/UObject/PropertyTag.cpp` | FPropertyTag 序列化实现、LoadPropertyTagNoFullType 函数 |
| `Runtime/CoreUObject/Private/UObject/Class.cpp` | SerializeTaggedProperties 使用 FPropertyTag |

### 版本判断

| 文件 | 内容 |
|------|------|
| `Runtime/Core/Public/UObject/ObjectVersion.h` | VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG、VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG、VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT、VAR_UE4_ARRAY_PROPERTY_INNER_TAGS |
| `Runtime/CoreUObject/Public/UObject/ObjectVersionUE5.h` | EUnrealEngineObjectUE5Version::PROPERTY_TAG_COMPLETE_TYPE_NAME、PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION |

### 关键方法

| 方法 | 源码位置 | 说明 |
|------|----------|------|
| `FPropertyTag::SerializeTaggedProperty` | PropertyTag.cpp | 序列化属性值 |
| `operator<<(FArchive&, FPropertyTag&)` | PropertyTag.cpp | Tag 序列化入口 |
| `LoadPropertyTagNoFullType` | PropertyTag.cpp | 旧版本部分类型名加载 |
| `SerializePropertyTagAsText` | PropertyTag.cpp | 文本格式序列化 |
| `SetType` | PropertyTag.cpp | 设置完整类型名并填充废弃字段 |

## 版本差异

### UE5.4 类型名系统变更

**新增字段：** TypeName (FPropertyTypeName)

**废弃字段（5.4 开始废弃）：**
- Prop → 使用 GetProperty()/SetProperty()
- StructName → 使用 GetType().GetParameterName(0) 或 GetType().IsStruct(StructName)
- StructGuid → 使用 GetType().GetParameterName(1)
- EnumName → 使用 GetType().IsEnum(EnumName) 或 GetType().GetParameterName(0)
- InnerType → 使用 GetType().GetParameterName(0)
- ValueType → 使用 GetType().GetParameterName(1)

**版本判断：** UE5.4+ 使用完整类型名（EUnrealEngineObjectUE5Version::PROPERTY_TAG_COMPLETE_TYPE_NAME），通过 Slot << SA_ATTRIBUTE(TEXT("Type"), Tag.TypeName) 序列化，加载时调用 Tag.SetType(Tag.TypeName)；旧版本使用部分类型名，调用 LoadPropertyTagNoFullType(Slot, Tag) 读取 Type + 各类型特定字段。

### UE5 属性扩展机制

**新增版本：** EUnrealEngineObjectUE5Version::PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION

**新增字段：**
- SerializeType — 序列化类型标记
- OverrideOperation — 重写操作标记
- bExperimentalOverridableLogic — 实验性重写逻辑标记

**新增标志（EPropertyTagFlags）：**
- HasPropertyExtensions — 有扩展数据
- HasBinaryOrNativeSerialize — 二进制/原生序列化
- SkippedSerialize — 跳过序列化
- BoolTrue — 布尔值为 true（与 BoolVal 合并）

### UE4 版本里程碑

| 版本号 | 说明 |
|--------|------|
| VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG | PropertyGuid 字段支持 |
| VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG | StructGuid 字段支持（StructProperty） |
| VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT | SetProperty/MapProperty 类型支持 |
| VAR_UE4_ARRAY_PROPERTY_INNER_TAGS | ArrayProperty InnerType 字段支持 |

### 版本兼容处理

**加载流程：**
1. 检查 Version >= PROPERTY_TAG_COMPLETE_TYPE_NAME
2. 新版本：读取完整 TypeName
3. 旧版本：读取 Type + 类型特定字段（StructName/EnumName/InnerType/ValueType）
4. 检查 HasPropertyGuid 标志，读取 PropertyGuid
5. 检查 HasPropertyExtensions 标志，读取扩展字段

**保存流程：**
1. 填充 TypeName（从 Property 构造）
2. 计算 SerializeType（Property/BinaryOrNative/Skipped）
3. 设置 PropertyTagFlags（HasArrayIndex/HasPropertyGuid/HasPropertyExtensions 等）
4. 记录 SizeOffset（用于回写实际 Size）

---

*Source: Runtime/CoreUObject/Public/UObject/PropertyTag.h, Runtime/CoreUObject/Private/UObject/PropertyTag.cpp*
*Document created: Phase 2-03 (SERI-03)*