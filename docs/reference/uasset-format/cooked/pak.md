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
[数据区 - FPakEntry + 数据]   — 交错存储：条目头 + 实际数据（压缩/加密）
[数据区 - FPakEntry + 数据]
...
[索引区 - DirectoryIndex]     — 文件尾索引定位（目录树结构）
[FPathHashIndex]              — PathHash 索引（Version 10+）
[EncodedPakEntries]           — 编码的 FPakEntry 数据（Version 10+）
[FPakInfo]                    — 文件尾信息（魔数、版本、索引偏移）
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
| PakFile_Version_FrozenIndex | 9 | 已废弃，不再支持 |
| PakFile_Version_PathHashIndex | 10 | PathHash 索引 |
| PakFile_Version_Fnv64BugFix | 11 | Fnv64 哈希修复 |
| PakFile_Version_Utf8PakDirectory | 12 | UTF8 目录名 |

---

## FPakInfo 字段表

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| Magic | uint32 | 魔数 0x5A6F12E1 | 所有版本 |
| Version | int32 | Pak 版本号 | 所有版本 |
| IndexOffset | int64 | 索引在文件中的偏移 | 所有版本 |
| IndexSize | int64 | 索引大小 | 所有版本 |
| IndexHash | FSHAHash | 索引 SHA1 哈希（20 字节） | 所有版本 |
| bEncryptedIndex | uint8 | 索引是否加密 | Version 4+ |
| EncryptionKeyGuid | FGuid | 加密密钥 GUID | Version 7+ |
| CompressionMethods | TArray<FName> | 压缩方法列表 | Version 8+ |

**固定常量：**
- `PakFile_Magic = 0x5A6F12E1` — 魔数
- `MaxChunkDataSize = 64KB` — 最大压缩块大小
- `CompressionMethodNameLen = 32` — 压缩方法名长度
- `MaxNumCompressionMethods = 5` — 最大压缩方法数量

---

## FPakEntry 字段表

| 字段名 | 类型 | 用途 | 版本差异 |
|--------|------|------|----------|
| Offset | int64 | 文件在 Pak 中的偏移 | 所有版本 |
| Size | int64 | 序列化大小（压缩后） | 所有版本 |
| UncompressedSize | int64 | 原始大小 | 所有版本 |
| Hash[20] | uint8[] | 文件 SHA1 哈希 | 所有版本 |
| CompressionBlocks | TArray<FPakCompressedBlock> | 压缩块数组 | Version 3+ |
| CompressionBlockSize | uint32 | 压缩块大小 | Version 3+ |
| CompressionMethodIndex | uint32 | 压缩方法索引 | Version 3+ |
| Flags | uint8 | 条目标志 | 所有版本 |

**Flags 标志：**
| 标志 | 值 | 说明 |
|------|-----|------|
| Flag_None | 0x00 | 无标志 |
| Flag_Encrypted | 0x01 | 文件已加密 |
| Flag_Deleted | 0x02 | 文件已删除（DeleteRecords） |

**版本差异说明：**
- Version 1: 不包含压缩相关字段
- Version 2: 移除时间戳字段（Timestamp）
- Version 3+: 添加 CompressionBlocks、CompressionBlockSize、CompressionMethodIndex

---

## FPakCompressedBlock 字段表

| 字段名 | 类型 | 用途 |
|--------|------|------|
| CompressedStart | int64 | 块起始偏移 |
| CompressedEnd | int64 | 块结束偏移 |

**偏移计算（Version 5+）：**
- Version 5+: 相对于压缩数据起始位置
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

**编码方式：**

| 状态 | 值范围 | 说明 |
|------|--------|------|
| Invalid | 0x80000000 (MIN_int32) | 无效位置 |
| OffsetIntoEncoded | 0x00000000 - 0x7FFFFFFE | EncodedPakEntries 中的偏移 |
| ListIndex | 0x80000001 - 0xFFFFFFFF | 文件索引（取负值减 1） |

**解析方法：**
- `IsInvalid()`: Index == 0x80000000
- `GetOffsetIntoEncoded()`: Index（当在 0x00000000-0x7FFFFFFE 范围）
- `GetListIndex()`: -(Index + 1)（当在 0x80000001-0xFFFFFFFF 范围）

---

## FDirectoryIndex 结构

| 类型 | 定义 | 用途 |
|------|------|------|
| FDirectoryIndex | TMap<FString, FPakDirectory> | 目录名到文件列表映射 |
| FPakDirectory | TMap<FUtf8String, FPakEntryLocation> | 文件名到条目位置映射 |

**目录树结构：**
```
FDirectoryIndex:
  "/" → FPakDirectory: {"Game.uasset" → FPakEntryLocation}
  "/Content" → FPakDirectory: {"Character.uasset" → FPakEntryLocation}
  "/Content/Models" → FPakDirectory: {"Hero.uasset" → FPakEntryLocation}
```

---

## FPathHashIndex 结构（Version 10+）

| 类型 | 定义 | 用途 |
|------|------|------|
| FPathHashIndex | TMap<uint64, FPakEntryLocation> | 文件路径哈希到条目位置映射 |
| EncodedPakEntries | TArray<uint8> | 编码的 FPakEntry 数据 |

**PathHash 算法：**
- 使用 Fnv64 哈希计算文件路径的哈希值
- Version 11+: 修复 Fnv64 哈希 bug

**EncodedPakEntries 说明：**
- 存储 FPakEntry 的紧凑编码版本
- 通过 FPakEntryLocation.GetOffsetIntoEncoded() 定位
- 减少 FPakEntry 序列化开销

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
| FPakSignatureFile | Runtime/PakFile/Public/FPakSignatureFile.h |
| Pak 挂载实现 | Runtime/PakFile/Private/PakFile.cpp |

---

## 版本差异

**Version 2+:**
- 移除时间戳字段（Timestamp）
- 减少序列化开销

**Version 3+:**
- 添加压缩加密支持
- FPakEntry 包含 CompressionBlocks、CompressionBlockSize、CompressionMethodIndex

**Version 7+:**
- 添加 EncryptionKeyGuid 字段
- 支持多个加密密钥

**Version 8+:**
- 使用 FName 压缩方法名（替代索引）
- 支持 5 种压缩方法

**Version 10+:**
- 添加 PathHashIndex 机制
- EncodedPakEntries 编码存储
- 更高效的文件查找（哈希索引）

**Version 11+:**
- Fnv64 哈希 bug 修复
- 修正路径哈希计算

**Version 12+:**
- 支持 UTF8 目录名
- 使用 FUtf8String 替代 FString

---

## Pak 签名机制

**FPakSignatureFile 结构：**
- 存储 Pak 文件的签名数据
- 用于验证 Pak 文件完整性

**签名验证：**
- 验证 FPakInfo 签名
- 验证索引区签名
- 防止 Pak 文件篡改

---

## Pak 与 IoStore 对比

| 特性 | Pak | IoStore |
|------|-----|---------|
| 文件组织 | 单文件容器 | TOC + 数据分离 |
| 数据拆分 | 整文件存储 | Chunk 拆分存储 |
| 索引方式 | DirectoryIndex + PathHashIndex | DirectoryIndex + PerfectHash |
| 版本数量 | 12 个版本 | 8 个版本 |
| UE5 推荐 | 兼容支持 | 主要格式 |
| 加密支持 | AES | AES |
| 压缩支持 | Oodle/Zlib | Oodle/Zlib |
| 签名支持 | FPakSignatureFile | SignatureHash + ChunkBlockSignatures |

---

## 交叉引用

- Cooked vs Uncooked 对比见 [cooked/cooked-vs-uncooked.md](cooked-vs-uncooked.md)
- IoStore 格式见 [cooked/iostore.md](iostore.md)
- 文件头结构见 [package-summary.md](../package-summary.md)
- 序列化机制见 [serialization/linker-load.md](../serialization/linker-load.md)