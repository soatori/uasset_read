# 文件尾结构 (PackageTrailer)

## 概述

PackageTrailer 是 UE5 新增的文件尾结构，存储在 .uasset 文件末尾，用于管理 Payload 数据。结构为：[Header] + [Payload Data] + [Footer]。Footer 以 PACKAGE_FILE_TAG 结尾，用于文件验证。

PackageTrailer 的详细内容（版本演进、虚拟化机制）在 Phase 7（版本演进历史）处理，此处仅简要说明存在和位置。

## Header 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| HeaderTag | uint64 | 魔数 0xD1C43B2E80A5F697 |
| Version | int32 | Trailer 版本号 |
| HeaderLength | uint32 | Header 大小 |
| PayloadsDataLength | uint64 | Payload 数据总大小 |
| NumPayloads | uint32 | Payload 数量 |
| PayloadLookupTable | TArray<FLookupTableEntry> | Payload 查找表 |

**PayloadLookupTable**: 详见 [bulkdata-region.md](bulkdata-region.md) FLookupTableEntry 结构。

## Footer 结构

| 字段名 | 类型 | 用途 |
|--------|------|------|
| FooterTag | uint64 | 魔数 0x29BFCA045138DE76 |
| TrailerLength | uint64 | Trailer 总大小 |
| PackageTag | uint32 | PACKAGE_FILE_TAG (0x9E2A83C1) |

**PACKAGE_FILE_TAG**: Footer 以文件魔数结尾，形成双重验证。

## 源码引用

- Runtime/CoreUObject/Public/UObject/PackageTrailer.h
- Runtime/Core/Public/UObject/ObjectVersion.h

## 版本差异

### UE5 新增
- PackageTrailer 为 UE5 特有结构
- UE4 文件无 Trailer，文件末尾直接以 PACKAGE_FILE_TAG 结尾
- PAYLOAD_TOC 版本引入 Trailer 机制

### 与 BulkData 关系
- PayloadLookupTable 承载 PayloadTOC 数据
- 详见 [bulkdata-region.md](bulkdata-region.md) PayloadTOC 结构

详见 [file-structure.md](file-structure.md) 整体结构概述。