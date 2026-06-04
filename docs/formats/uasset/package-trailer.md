# 文件尾结构 (PackageTrailer)

## 概述

PackageTrailer 是 UE5 新增的文件尾结构，存储在 .uasset 文件末尾，用于管理 Payload 数据（BulkData 虚拟化前的本地存储）。

结构为：`[Header] + [Payload Data] + [Footer]`。

- **Header**: 包含版本号、Payload 数据总大小和 Payload 条目数量
- **Payload Data**: 实际的 Payload 数据块
- **Footer**: 包含 Footer 标记和校验信息

## PackageTrailer Header

Header 位于文件尾部，结构如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| Version | uint32 | PackageTrailer 版本号 |
| PayloadDataSize | uint64 | Payload 数据总大小 |
| PayloadDataCount | uint32 | Payload 条目数量 |

## PackageTrailer Footer

Footer 位于文件最末尾，用于验证 Trailer 的完整性：

| 字段 | 类型 | 说明 |
|------|------|------|
| FooterTag | uint32 | Footer 标记 (PACKAGE_TRAILER_FOOTER_TAG) |
| Reserved | uint32 | 保留字段 |

## 定位 PackageTrailer

PackageTrailer 的位置通过 FPackageFileSummary 中的 PayloadTocOffset 字段确定：

- **UE5 >= PAYLOAD_TOC (1002)**: PayloadTocOffset 指向 PackageTrailer 的 Header
- **UE5 < PAYLOAD_TOC (1002)**: 文件中不存在 PackageTrailer

## Payload 条目

每个 Payload 条目描述一个独立的 Payload 数据块：

| 字段 | 类型 | 说明 |
|------|------|------|
| Offset | uint64 | Payload 数据在文件中的偏移 |
| Size | uint64 | Payload 数据大小 |
| Flags | uint32 | Payload 标志 |
| DataType | FName | 数据类型名称 |

## 源码引用

- `Runtime/CoreUObject/Public/UObject/PackageTrailer.h` — PackageTrailer 结构定义
- `Runtime/CoreUObject/Private/UObject/PackageTrailer.cpp` — PackageTrailer 序列化实现
