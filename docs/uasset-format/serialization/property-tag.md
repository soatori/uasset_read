# FPropertyTag 属性标签

## 概述

FPropertyTag 是属性序列化的元数据结构，用于在 UObject 序列化过程中描述每个属性的名称、类型、大小等信息。每个属性在序列化时都会先写入一个 FPropertyTag，然后再写入实际的属性数据。

FPropertyTag 在加载流程中由 [LinkerLoad](linker-load.md) 的 Preload 阶段解析。

## 结构体定义

```cpp
struct FPropertyTag {
    FName Name;              // 属性名称
    uint32 Flags;            // 属性标志（REP_Replicated 等）
    uint8 ArrayIndex;        // 数组索引（用于动态数组属性）
    // 版本相关字段见下方
};
```

## 序列化字段

### 基础字段（所有版本）

| 字段 | 类型 | 说明 |
|------|------|------|
| Name | FName | 属性名称（FName 索引或内联字符串） |
| Flags | uint32 | 属性标志（如 REP_Replicated） |
| ArrayIndex | uint8 | 数组索引，用于区分动态数组中的元素 |

### 版本相关字段

| 字段 | 版本条件 | 说明 |
|------|----------|------|
| StructGuid | UE4 >= VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG (336) | 结构体类型的 GUID，用于版本兼容 |
| HasPropertyType | — | 如果 Name 为 NAME_None，则内联写入属性类型名 |
| ContainerType | 当属性为 Set/Map 时 | 容器类型信息 |

## 属性类型

FPropertyTag 通过 Type 字段标识属性数据的类型。常见属性类型包括：

| 类型名 | 说明 |
|--------|------|
| BoolProperty | 布尔值 |
| IntProperty | 整型 |
| FloatProperty | 浮点型 |
| StrProperty | 字符串 |
| NameProperty | FName |
| ObjectProperty | 对象引用 |
| StructProperty | 结构体 |
| ArrayProperty | 动态数组 |
| MapProperty | 映射表 |
| SetProperty | 集合 |
| EnumProperty | 枚举 |
| ByteProperty | 字节/枚举 |

## 序列化顺序

```
Name (FName)
Flags (uint32)
ArrayIndex (uint8)
[StructGuid (FGuid) — 当 UE4 >= 336 且属性类型为 StructProperty]
[HasPropertyType (bool) — 当 Name == NAME_None]
[PropertyType (FName) — 当 HasPropertyType == true]
[容器类型信息 — 当属性为 Set/Map]
```

## 源码引用

- `Runtime/CoreUObject/Private/UObject/PropertyTag.cpp` — FPropertyTag 序列化实现
- `Runtime/CoreUObject/Public/UObject/PropertyTag.h` — FPropertyTag 结构定义
- `Runtime/Core/Public/UObject/ObjectVersion.h` — VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG 定义
