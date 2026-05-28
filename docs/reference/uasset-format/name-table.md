# 名称表结构

## 概述

名称表存储包内所有 FName 字符串的唯一标识。NameCount 指定名称数量，NameOffset 指定名称数据在文件中的起始位置。FName 由两部分组成：Index（名称入口编号）和 Number（实例编号），名称表按顺序编号，从 0 开始。

名称序列化通过 SerializeName 函数完成，读取 NameIndex 和 Number 两个值，通过 NameMap 映射到实际字符串。

## 字段表

### PackageFileSummary 中名称表定位字段

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| NameCount | int32 | 名称表条目数量 | — |
| NameOffset | int32 | 名称数据在文件中的偏移 | — |
| NamesReferencedFromExportDataCount | int32 | 从导出数据引用的名称数量 | UE5 新增 |

### FName 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Index | int32 | 名称入口编号（指向名称表中第几个条目） |
| Number | int32 | 实例编号（用于区分同名不同实例，如 Material_0, Material_1） |

### 名称表条目序列化格式

每个名称条目序列化为：
- NameString (FString) - 名称字符串
- NonCasePreservingHash (uint16) - 非大小写保留哈希（旧版本）
- CasePreservingHash (uint16) - 大小写保留哈希

## 序列化机制

名称通过 `operator<<(FArchive& Ar, FName& Name)` 序列化：
1. 读取 NameIndex (int32)
2. 读取 Number (int32)
3. NameIndex 指向 NameMap 中的条目，获取实际字符串
4. Number 用于区分同名的不同实例

**NameMap**: 加载时建立，TMap<FName, int32> 类型，将 FName 映射到名称表索引。

**入口编号规则**: 名称表按文件顺序编号，Index 值直接对应条目位置（从 0 开始）。

## 源码引用

- Runtime/CoreUObject/Public/UObject/PackageFileSummary.h (NameCount/NameOffset)
- Runtime/CoreUObject/Public/UObject/LinkerLoad.h (NameMap)
- Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp (SerializeName 实现)

## 版本差异

### UE5 新增
- **NamesReferencedFromExportDataCount**: NAMES_REFERENCED_FROM_EXPORT_DATA 版本新增，用于优化加载，仅加载必要的名称

### 历史变更
- VER_UE4_NAME_HASHES_SERIALIZED: 名称哈希序列化版本
- VER_UE4_SERIALIZE_NAME_IN_UNICODE: Unicode 名称序列化
- 名称条目格式随版本扩展

详见 [file-structure.md](file-structure.md) 整体结构概述。