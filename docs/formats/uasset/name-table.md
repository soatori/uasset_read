# 名称表结构

## 概述

名称表存储包内所有 FName 字符串的唯一标识。NameCount 指定名称数量，NameOffset 指定名称数据在文件中的起始位置。FName 由三部分组成：ComparisonIndex（名称入口编号，用于比较）、DisplayIndex（显示用名称入口编号，仅 WITH_CASE_PRESERVING_NAME 构建时存在）和 Number（实例编号），名称表按顺序编号，从 0 开始。

名称序列化通过 FLinkerLoad::operator<<(FName&) 完成，读取 NameIndex 和 Number 两个值，通过 NameMap（TArray<FNameEntryId>）映射到实际字符串。

## 字段表

### PackageFileSummary 中名称表定位字段

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| NameCount | int32 | 名称表条目数量 | — |
| NameOffset | int32 | 名称数据在文件中的偏移 | — |
| NamesReferencedFromExportDataCount | int32 | 从导出数据引用的名称数量 | UE5 NAMES_REFERENCED_FROM_EXPORT_DATA 版本新增 |

### FName 结构（运行时）

| 字段名 | 类型 | 用途 | 备注 |
|--------|------|------|------|
| ComparisonIndex | FNameEntryId | 名称入口编号（用于比较和查找） | 始终存在 |
| Number | uint32 | 实例编号（用于区分同名不同实例，如 Material_0, Material_1） | 内部存储为实例编号+1，零初始化表示无实例编号；UE_FNAME_OUTLINE_NUMBER 构建时不存在于内存布局中 |
| DisplayIndex | FNameEntryId | 显示用名称入口编号（保留大小写） | 仅 WITH_CASE_PRESERVING_NAME 构建时存在 |

**注意**: FNameEntryId 是一个包装 uint32 的类型，不是 int32。序列化时 NameIndex 使用 int32，Number 使用 int32。

### 名称表条目序列化格式（FNameEntrySerialized）

每个名称条目序列化为：
- StringLen (int32) - 字符串长度，正数表示 ANSI 字符串，负数表示宽字符串（绝对值为长度）
- StringData - 字符串数据（ANSICHAR * StringLen 或 WIDECHAR * |StringLen|）
- NonCasePreservingHash (uint16) - 非大小写保留哈希（仅 VER_UE4_NAME_HASHES_SERIALIZED 及之后版本）
- CasePreservingHash (uint16) - 大小写保留哈希（仅 VER_UE4_NAME_HASHES_SERIALIZED 及之后版本）

## 序列化机制

### FName 序列化（FLinkerLoad::operator<<）

1. 读取 NameIndex (int32)
2. 读取 Number (int32)
3. NameIndex 指向 NameMap 中的条目，获取 FNameEntryId
4. 使用 FName::CreateFromDisplayId(MappedName, Number) 创建 FName

**NameMap**: FLinkerLoad 中的 TArray<FNameEntryId> 类型，在 SerializeNameMap() 中建立。每个条目是 FNameEntrySerialized 反序列化后构建的 FName 的 DisplayIndex。

**入口编号规则**: 名称表按文件顺序编号，NameIndex 值直接对应条目位置（从 0 开始）。

### 名称表序列化（FLinkerLoad::SerializeNameMap）

1. 定位到 Summary.NameOffset
2. 预缓存名称、导入和导出映射数据
3. 循环读取 NameCount 个 FNameEntrySerialized 条目
4. 每个条目通过 operator<<(FArchive&, FNameEntrySerialized&) 反序列化
5. 构建 FName 并将其 DisplayIndex 存入 NameMap

### FNameEntrySerialized 反序列化（operator<<(FArchive&, FNameEntrySerialized&)）

1. 读取 StringLen (int32)
2. 如果 StringLen < 0，则为宽字符串，取绝对值
3. 读取字符串数据（ANSICHAR 或 WIDECHAR）
4. 如果版本 >= VER_UE4_NAME_HASHES_SERIALIZED，读取两个 uint16 哈希值
5. 哈希值在加载时不再使用，仅保持序列化格式兼容性

## 源码引用

- Runtime/CoreUObject/Public/UObject/PackageFileSummary.h (NameCount/NameOffset/NamesReferencedFromExportDataCount)
- Runtime/CoreUObject/Public/UObject/LinkerLoad.h (NameMap, FLinkerLoad::operator<<(FName&))
- Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp (SerializeNameMap 实现)
- Runtime/Core/Public/UObject/NameTypes.h (FName, FNameEntryId, FNameEntrySerialized 定义)
- Runtime/Core/Private/UObject/UnrealNames.cpp (operator<<(FArchive&, FNameEntrySerialized&) 实现)
- Runtime/Core/Public/UObject/ObjectVersion.h (VER_UE4_NAME_HASHES_SERIALIZED, EUnrealEngineObjectUE5Version)

## 版本差异

### UE5 新增
- **NAMES_REFERENCED_FROM_EXPORT_DATA** (EUnrealEngineObjectUE5Version): 支持剥离未从导出数据引用的名称，用于优化加载，仅加载必要的名称
- **PAYLOAD_TOC**: 在包摘要中添加了 payload 目录表

### 历史变更
- **VER_UE4_CASE_PRESERVING_FNAME**: FName 改为大小写保留，引入 DisplayIndex 字段
- **VER_UE4_NAME_HASHES_SERIALIZED**: 名称哈希改为在保存时计算并序列化，而非加载时计算；名称条目格式增加了两个 uint16 哈希字段

### 关于 Unicode 名称
- 源码中不存在 `VER_UE4_SERIALIZE_NAME_IN_UNICODE` 常量
- 宽字符串支持通过 StringLen 的符号（负值表示宽字符串）实现，这是 FNameEntrySerialized 的固有设计，不受特定版本常量控制
- 详见 [file-structure.md](file-structure.md) 整体结构概述。