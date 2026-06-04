# Pak 文件格式文档

## 概述

**Pak 是 UE 长期使用的打包容器格式**，在 UE4 和 UE5 中仍然支持，是传统的数据打包方式。

**文件组织：**
- 数据区：交错存储（条目头 FPakEntry + 实际数据）
- 索引区：文件尾定位（DirectoryIndex、FPakInfo）

**与 .uasset 关系：** .uasset 作为文件条目存储在 Pak 中，每个条目对应一个完整的 .uasset 文件（不同于 IoStore 的 Chunk 拆分）。

**UE5 中的地位：** IoStore 是主要推荐格式，Pak 作为兼容支持。某些场景仍使用 Pak 格式（如某些插件包、向后兼容需求）。

---

## 文件结构图

### .pak 文件结构

```
[数据区 - FPakEntry + 数据]    — 交错存储：条目头 + 实际数据（压缩/加密）
[数据区 - FPakEntry + 数据]
...
[索引区 - DirectoryIndex]      — 文件尾索引定位（目录树结构）
[FPathHashIndex]               — PathHash 索引（Version 10+）
[EncodedPakEntries]            — 编码的 FPakEntry 数据（Version 10+）
[FPakInfo]                     — 文件尾信息（魔数、版本、索引偏移）
```

**定位方式：**
- 从文件尾读取 FPakInfo，获取 IndexOffset
- 根据 IndexOffset 定位索引区
- 通过 DirectoryIndex 或 PathHashIndex 查找文件

---

## FPakInfo 版本枚举

| 版本 | 值 | 说明 |
|------|-----|------|
| PakFile_Version_Initial | 1 | 初始版本 |
| PakFile_Version_NoTimestamps | 2 | 移除时间戳字段 |
| PakFile_Version_CompressionEncryption | 3 | 添加压缩加密支持 |
| PakFile_Version_IndexEncryption | 4 | 索引加密支持 |
| PakFile_Version_RelativeChunkOffsets | 5 | 相对偏移（压缩块偏移相对于数据起始） |
| PakFile_Version_DeleteRecords | 6 | 删除记录支持 |
| PakFile_Version_EncryptionKeyGuid | 7 | 加密密钥 GUID |
| PakFile_Version_FNameBasedCompressionMethod | 8 | FName 压缩方法名 |
| PakFile_Version_FrozenIndex | 9 | **已废弃，不再支持**（遇到会 Fatal 错误） |
| PakFile_Version_PathHashIndex | 10 | PathHash 索引 |
| PakFile_Version_Fnv64BugFix | 11 | Fnv64 哈希修复 |
| PakFile_Version_Utf8PakDirectory | 12 | UTF8 目录名 |

**辅助常量：**
- `PakFile_Version_Last` — 最后一个版本标记
- `PakFile_Version_Latest = PakFile_Version_Last - 1` — 最新可用版本
- `PakFile_Version_Invalid` — 无效版本标记

**注意：** `PakFile_Version_FrozenIndex (9)` 已被废弃，如果 Pak 文件使用此版本创建，加载时会触发 Fatal 错误并提示 "Regenerate Paks"。

---

## FPakInfo 字段表

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| Magic | uint32 | 魔数 0x5A6F12E1 | 所有版本 |
| Version | int32 | Pak 版本号 | 所有版本 |
| IndexOffset | int64 | 索引在文件中的偏移 | 所有版本 |
| IndexSize | int64 | 索引大小（字节） | 所有版本 |
| IndexHash | FSHAHash | 索引 SHA1 哈希（20 字节），用于检查加载时的数据损坏 | 所有版本 |
| bEncryptedIndex | uint8 | 索引是否加密 | Version 4+ |
| EncryptionKeyGuid | FGuid | 加密密钥 GUID。为空时使用内嵌密钥 | Version 7+ |
| CompressionMethods | TArray<FName> | 压缩方法列表（保存为 FString） | Version 8+ |

**源码定义：** `struct FPakInfo`，位于 `Runtime/PakFile/Public/IPlatformFilePak.h`

**固定常量：**
- `PakFile_Magic = 0x5A6F12E1` — 魔数
- `MaxChunkDataSize = 64KB` — 最大压缩块大小
- `CompressionMethodNameLen = 32` — 压缩方法名长度
- `MaxNumCompressionMethods = 5` — 最大压缩方法数量

**序列化大小计算：**
```
GetSerializedSize(InVersion) = sizeof(Magic) + sizeof(Version) + sizeof(IndexOffset)
                             + sizeof(IndexSize) + sizeof(IndexHash) + sizeof(bEncryptedIndex)
                             + (InVersion >= 7 ? sizeof(EncryptionKeyGuid) : 0)
                             + (InVersion >= 8 ? CompressionMethodNameLen * MaxNumCompressionMethods : 0)
                             + (InVersion >= 9 && InVersion < 10 ? sizeof(bool) : 0)  // bIndexIsFrozen
```

---

## FPakEntry 字段表

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| Offset | int64 | 文件在 Pak 中的偏移 | 所有版本 |
| Size | int64 | 序列化大小（压缩后） | 所有版本 |
| UncompressedSize | int64 | 原始大小 | 所有版本 |
| Hash[20] | uint8[] | 文件 SHA1 哈希 | 所有版本 |
| CompressionMethodIndex | uint32 | 压缩方法索引 | 所有版本 |
| CompressionBlocks | TArray<FPakCompressedBlock> | 压缩块数组 | Version 3+（仅当 CompressionMethodIndex != 0 时序列化） |
| Flags | uint8 | 条目标志 | Version 3+ |
| CompressionBlockSize | uint32 | 压缩块大小 | Version 3+ |
| Verified | mutable bool | 文件头是否已验证（不序列化） | 所有版本 |

**源码定义：** `struct FPakEntry`，位于 `Runtime/PakFile/Public/IPlatformFilePak.h`

**Flags 标志：**
| 标志 | 值 | 说明 |
|------|-----|------|
| Flag_None | 0x00 | 无标志 |
| Flag_Encrypted | 0x01 | 文件已加密 |
| Flag_Deleted | 0x02 | 文件已删除（DeleteRecords） |

**序列化顺序（Serialize 方法）：**
1. Offset
2. Size
3. UncompressedSize
4. CompressionMethodIndex（Version 8+ 直接序列化；旧版本使用 int32 并转换）
5. Timestamp（仅 Version 1）
6. Hash[20]
7. CompressionBlocks（Version 3+，仅当 CompressionMethodIndex != 0 时）
8. Flags（Version 3+）
9. CompressionBlockSize（Version 3+）

**版本差异说明：**
- Version 1: 不包含压缩相关字段，包含 Timestamp
- Version 2: 移除时间戳字段（Timestamp）
- Version 3+: 添加 CompressionBlocks、CompressionBlockSize、Flags
- Version 8+: CompressionMethod 从 int32 枚举改为 FName 索引

---

## FPakCompressedBlock 字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| CompressedStart | int64 | 块起始偏移（相对压缩数据起始位置） |
| CompressedEnd | int64 | 块结束偏移（相对压缩数据起始位置） |

**源码定义：** `struct FPakCompressedBlock`，位于 `Runtime/PakFile/Public/IPlatformFilePak.h`

**偏移计算（Version 5+）：**
- Version 5+: 相对于压缩数据起始位置（IndexOffset 之后的数据区）
- Version < 5: 绝对文件偏移

**数据定位：**
```
块数据位置 = FPakEntry.Offset + CompressedStart
块数据大小 = CompressedEnd - CompressedStart
```

---

## FPakEntryLocation 字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Index | int32 | 内部索引值 |

**源码定义：** `struct FPakEntryLocation`，位于 `Runtime/PakFile/Public/IPlatformFilePak.h`

**编码方式：**

| 状态 | 值范围 | 说明 |
|------|--------|------|
| Invalid | 0x80000000 (MIN_int32) | 无效位置 |
| Unused (Invalid) | 0x7FFFFFFF (MAX_int32 - 1) | 未使用，视为无效 |
| OffsetIntoEncoded | 0x00000000 - 0x7FFFFFFE | EncodedPakEntries 中的偏移 |
| ListIndex | 0x80000001 - 0xFFFFFFFF | 文件索引（取负值减 1） |

**常量定义：**
- `Invalid = MIN_int32` (0x80000000)
- `MaxIndex = MAX_int32 - 1` (0x7FFFFFFE)

**解析方法：**
- `IsInvalid()`: Index <= Invalid || Index > MaxIndex
- `IsOffsetIntoEncoded()`: 0 <= Index && Index <= MaxIndex
- `IsListIndex()`: (-MaxIndex - 1) <= Index && Index <= -1
- `GetAsOffsetIntoEncoded()`: 如果有效则返回 Index，否则返回 -1
- `GetAsListIndex()`: -(Index + 1)（当为 ListIndex 时）

---

## FDirectoryIndex 结构

| 类型 | 定义 | 用途 |
|------|------|------|
| FDirectoryIndex | TMap<FString, FPakDirectory> | 目录名到文件列表映射 |
| FPakDirectory | TMap<FUtf8String, FPakEntryLocation> | 文件名到条目位置映射 |

**源码定义：** 位于 `Runtime/PakFile/Public/IPlatformFilePak.h`

**目录树结构：**
```
FDirectoryIndex:
  "/" → FPakDirectory: {"Game.uasset" → FPakEntryLocation}
  "/Content" → FPakDirectory: {"Character.uasset" → FPakEntryLocation}
  "/Content/Models" → FPakDirectory: {"Hero.uasset" → FPakEntryLocation}
```

**DirectoryTreeIndex（可选）：**
- 通过 `ENABLE_PAKFILE_USE_DIRECTORY_TREE` 宏控制（默认启用）
- 使用 `TDirectoryTree<FPakDirectory>` 替代 `TMap<FString, FPakDirectory>` 提升查询性能

---

## FPathHashIndex 结构（Version 10+）

| 类型 | 定义 | 用途 |
|------|------|------|
| FPathHashIndex | TMap<uint64, FPakEntryLocation> | 文件路径哈希到条目位置映射 |
| EncodedPakEntries | TArray<uint8> | 编码的 FPakEntry 数据 |

**源码定义：** 位于 `Runtime/PakFile/Public/IPlatformFilePak.h`

**PathHash 算法：**
- 使用 `FPakFile::HashPath(RelativePathFromMount, PathHashSeed, PakFileVersion)` 计算
- Version 11+: 修复 Fnv64 哈希 bug
- 每个 Pak 文件使用不同的 `PathHashSeed`（基于文件名生成），确保相同文件名在不同 Pak 中有不同的哈希

**EncodedPakEntries 说明：**
- 存储 FPakEntry 的紧凑编码版本
- 通过 FPakEntryLocation.GetAsOffsetIntoEncoded() 定位
- 减少 FPakEntry 序列化开销

**Index 设置：**
- `FPakFile::IsPakWritePathHashIndex()` — 控制是否写入 PathHashIndex
- `FPakFile::IsPakWriteFullDirectoryIndex()` — 控制是否写入完整 DirectoryIndex

---

## Pak 挂载流程

1. **FPakPlatformFile.Initialize：** 初始化 Pak 平台文件层
2. **FPakFile 构造：** 打开 .pak 文件，读取文件尾 FPakInfo
3. **验证魔数和版本：** 检查 Magic == 0x5A6F12E1，版本兼容性
4. **LoadIndex：** 根据 IndexOffset 定位并加载索引区
5. **解密索引（可选）：** 如果 bEncryptedIndex，使用 EncryptionKeyGuid 解密
6. **解析 DirectoryIndex：** 构建目录树结构
7. **解析 PathHashIndex（Version 10+）：** 构建路径哈希索引
8. **Mount：** 设置挂载点，加入 Pak 文件列表

---

## 数据读取流程

1. **FindFileInPakFiles：** 在挂载的 Pak 文件中查找
2. **路径查找：** 通过 DirectoryIndex 或 PathHashIndex 定位 FPakEntryLocation
3. **FPakEntry 定位：**
   - OffsetIntoEncoded：从 EncodedPakEntries 解码 FPakEntry
   - ListIndex：从预加载的 FPakEntry 列表获取
4. **FPakFileHandle 创建：** 创建文件句柄，处理压缩/加密
5. **解压/解密：**
   - 根据 CompressionMethodIndex 解压（Oodle/Zlib）
   - 根据 Flags 解密（AES）
6. **数据返回：** 返回解压后的原始数据

---

## 源码引用

| 结构 | 文件路径 |
|------|----------|
| FPakInfo | Runtime/PakFile/Public/IPlatformFilePak.h |
| FPakEntry | Runtime/PakFile/Public/IPlatformFilePak.h |
| FPakCompressedBlock | Runtime/PakFile/Public/IPlatformFilePak.h |
| FPakEntryLocation | Runtime/PakFile/Public/IPlatformFilePak.h |
| FPakFile | Runtime/PakFile/Public/IPlatformFilePak.h |
| FPakPlatformFile | Runtime/PakFile/Public/IPlatformFilePak.h |
| FPakSignatureFile | Runtime/PakFile/Public/IPlatformFilePak.h |
| FDirectoryIndex / FPakDirectory | Runtime/PakFile/Public/IPlatformFilePak.h |
| FPathHashIndex | Runtime/PakFile/Public/IPlatformFilePak.h |
| Pak 挂载实现 | Runtime/PakFile/Private/PakFile.cpp |

---

## 版本差异

**Version 2+:**
- 移除时间戳字段（Timestamp）
- 减少序列化开销

**Version 3+:**
- 添加压缩加密支持
- FPakEntry 包含 CompressionBlocks、CompressionBlockSize、Flags

**Version 4+:**
- 添加索引加密支持（bEncryptedIndex）

**Version 5+:**
- 压缩块偏移改为相对偏移（相对于压缩数据起始位置）

**Version 6+:**
- 添加删除记录支持（Flag_Deleted）

**Version 7+:**
- 添加 EncryptionKeyGuid 字段
- 支持多个加密密钥

**Version 8+:**
- 使用 FName 压缩方法名（替代 int32 索引）
- 支持最多 5 种压缩方法

**Version 9 (已废弃):**
- FrozenIndex 机制已废弃，不再支持
- 使用此版本创建的 Pak 加载时会触发 Fatal 错误

**Version 10+:**
- 添加 PathHashIndex 机制
- EncodedPakEntries 编码存储
- 更高效的文件查找（哈希索引）

**Version 11+:**
- Fnv64 哈希 bug 修复
- 修正路径哈希计算

**Version 12+:**
- 支持 UTF8 目录名
- FPakDirectory 使用 FUtf8String 替代 FString

---

## Pak 签名机制

**FPakSignatureFile 结构：**
- Magic: 0x73832DAA
- Version: EVersion（Invalid/First/Last/Latest）
- EncryptedHash: RSA 加密的哈希
- ChunkHashes: 每个 64KB 块的 CRC32 或 SHA1 哈希

**源码定义：** `struct FPakSignatureFile`，位于 `Runtime/PakFile/Public/IPlatformFilePak.h`

**签名验证：**
- 验证 FPakInfo 签名
- 验证索引区签名
- 防止 Pak 文件篡改
- 通过 `FPakPlatformFile::GetPakSignatureFile()` 获取签名文件

**哈希类型：**
- 可通过 `PAKHASH_USE_CRC` 宏选择 CRC32 或 SHA1
- 默认使用 CRC32（PAKHASH_USE_CRC = 1）

---

## Pak 与 IoStore 对比

| 特性 | Pak | IoStore |
|------|-----|---------|
| 文件组织 | 单文件容器 | TOC + 数据分离 |
| 数据拆分 | 整文件存储 | Chunk 拆分存储 |
| 索引方式 | DirectoryIndex + PathHashIndex | DirectoryIndex + PerfectHash |
| 版本数量 | 12 个版本 | 9 个有效版本 |
| UE5 推荐 | 兼容支持 | 主要格式 |
| 加密支持 | AES | AES |
| 压缩支持 | Oodle/Zlib | Oodle/Zlib |
| 签名支持 | FPakSignatureFile | SignatureHash + ChunkBlockSignatures |
| 哈希算法 | CRC32 或 SHA1（可配置） | BLAKE3-160 |

---

## 交叉引用

- Cooked vs Uncooked 对比见 [cooked/cooked-vs-uncooked.md](cooked-vs-uncooked.md)
- IoStore 格式见 [cooked/iostore.md](iostore.md)
- 文件头结构见 [package-summary.md](../package-summary.md)
- 序列化机制见 [serialization/linker-load.md](../serialization/linker-load.md)
