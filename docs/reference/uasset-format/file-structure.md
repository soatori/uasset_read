# .uasset 文件整体结构

## 概述

.uasset 是 Unreal Engine 的资产文件格式，存储单个 UPackage 的内容，包括导出对象和引用的外部对象。文件结构由 Header + Tables + Data + Trailer 组成，文件头 FPackageFileSummary 作为"目录"指向各数据区。文件以 PACKAGE_FILE_TAG (0x9E2A83C1) 验证。

.uasset 文件是 Unreal Engine 资产存储的基本单元，所有资产（材质、纹理、网格、蓝图等）均以 .uasset 格式保存。加载时，引擎首先读取文件头，根据偏移量定位各表，建立对象引用网络后按需加载对象数据。

## 文件布局示意图

```
┌─────────────────────────────────────────────┐
│ FPackageFileSummary (文件头)                │
│   - Tag, Version, Flags                     │
│   - NameOffset/Count, ExportOffset/Count... │
├─────────────────────────────────────────────┤
│ Name Table (名称表)                         │
│   - FName 条目序列                          │
├─────────────────────────────────────────────┤
│ Import Map (导入表)                         │
│   - FObjectImport 条目序列                  │
├─────────────────────────────────────────────┤
│ Export Map (导出表)                         │
│   - FObjectExport 条目序列                  │
├─────────────────────────────────────────────┤
│ Export Data (导出对象数据)                  │
│   - 各 Export 的序列化数据                  │
├─────────────────────────────────────────────┤
│ Bulk Data / Payload Data (数据区)           │
│   - 大型二进制数据                          │
├─────────────────────────────────────────────┤
│ PackageTrailer (文件尾，UE5新增)            │
│   - Header + Payload Data + Footer          │
│   - Footer 以 PACKAGE_FILE_TAG 结尾        │
└─────────────────────────────────────────────┘
```

## 各结构章节

### 文件头

详见 [package-summary.md](package-summary.md)

FPackageFileSummary 包含版本、表位置、数据位置等关键信息。文件头作为索引表，指向文件中各数据区的起始位置。

### 名称表

详见 [name-table.md](name-table.md)

存储包内所有 FName，由 NameOffset/NameCount 定位。FName 由 Index（入口编号）和 Number（实例编号）组成，通过 SerializeName 机制序列化。

### 导入表

详见 [import-export-tables.md](import-export-tables.md#import)

FObjectImport 序列，存储外部对象引用。每个 Import 条目记录对象名称、所属包、类名等信息。

### 导出表

详见 [import-export-tables.md](import-export-tables.md#export)

FObjectExport 序列，存储本包导出对象。每个 Export 条目记录对象名称、类引用、序列化数据位置等。

### 数据区

详见 [bulkdata-region.md](bulkdata-region.md)

三种数据存储方式：BulkData（传统）、PayloadTOC（UE5）、DataResource（UE5）。存储纹理像素、网格几何等大型二进制数据。

### 文件尾

详见 [package-trailer.md](package-trailer.md)

PackageTrailer (UE5新增)，以 PACKAGE_FILE_TAG 结尾。Header + Payload Data + Footer 结构，管理 Payload 数据。

## 加载流程概述

1. 读取 FPackageFileSummary，验证 PACKAGE_FILE_TAG
2. 根据版本号判断 UE4/UE5，选择对应解析策略
3. 读取 Name Table，建立名称映射（NameMap）
4. 读取 Import/Export Map，建立对象引用表
5. 按需加载 Export 数据和 Bulk Data（延迟加载）
6. UE5 文件还需解析 PackageTrailer 和 PayloadTOC

## 源码引用

- Runtime/CoreUObject/Public/UObject/PackageFileSummary.h
- Runtime/CoreUObject/Public/UObject/ObjectResource.h
- Runtime/CoreUObject/Public/UObject/PackageTrailer.h
- Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp（加载流程）