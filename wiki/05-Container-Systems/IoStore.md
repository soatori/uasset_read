---
title: IoStore 容器
section: iostore
---

# IoStore 容器

UE5.3+ 引入的新型容器格式，使用 `.utoc`（目录表）+ `.ucas`（数据容器）双文件结构替代传统 PAK 格式。IoStore 提供了 O(1) 的 Chunk 查找能力（Perfect Hash）、多分区支持、可选压缩/加密/签名，以及目录索引（按路径查找）。

> [!NOTE]
> IoStore 仅在 UE5.0+ 中可用，UE4 使用不同的存储机制。未烘焙/编辑器保存的资产可能仍使用传统 PAK 格式。

## 核心 API

```python
# 使用上下文管理器（推荐）
with IoStoreReader("game.utoc", "game.ucas") as reader:
    data = reader.read_chunk(FIoChunkId(bytes=chunk_id_bytes))

# 按路径提取（需要目录索引）
data = reader.extract_path("/Game/Maps/Level1.uasset")

# 列出所有文件
files = reader.list_files()
```

### IoStoreReader

```python
IoStoreReader(
    utoc_path: str,          # .utoc 文件路径（必需）
    ucas_path: str | None,   # .ucas 文件路径（可选，自动推导）
    aes_key: bytes | None,   # AES 解密密钥（可选）
    tolerant: bool = False,  # 宽容模式
    read_options: int = EIoStoreTocReadOptions.Default,
)

# 方法
.open()           -> None    # 打开容器，解析 TOC 头部、Chunk 数组、压缩块、目录索引
.close()          -> None    # 关闭所有文件句柄
.list_files()     -> List[str]          # 列出所有文件路径（需目录索引）
.does_chunk_exist(chunk_id) -> bool     # 检查 Chunk 是否存在
.try_resolve(chunk_id) -> Optional[Tuple[int, int]]  # 解析 Chunk -> (offset, length)
.extract(chunk_id_bytes) -> bytes        # 按 12 字节 ChunkId 提取数据
.extract_path(path: str) -> Optional[bytes]  # 按路径提取数据
.read_chunk(chunk_id) -> bytes           # 按 FIoChunkId 读取解压后数据
```

### IoStoreInfo

解析后的 TOC 摘要信息：

```python
info.version                    # TOC 版本（1-8）
info.toc_entry_count            # Chunk 数量
info.compressed_block_count     # 压缩块数量
info.compression_method_count   # 压缩方法数量
info.compression_block_size     # 压缩块大小（字节）
info.directory_index_size       # 目录索引大小
info.partition_count            # 分区数量
info.partition_size             # 分区大小
info.container_flags            # 容器标志（EIoContainerFlags）
info.is_encrypted               # 是否加密
info.is_compressed              # 是否压缩
info.chunk_ids                  # List[FIoChunkId]
info.chunk_offsets              # List[FIoOffsetAndLength]
```

## 核心结构

### FIoChunkId（12 字节）

Chunk 标识符，与 UE 源码 `FIoChunkId` 一致：

| 字节范围 | 字段 | 说明 |
|----------|------|------|
| 0-7 | ChunkId (uint64 LE) | 64 位 ID |
| 8-9 | ChunkIndex (uint16 BE) | Chunk 索引（大端序） |
| 10 | ChunkGroup (uint8) | Chunk 组 |
| 11 | ChunkType (uint8) | EIoChunkType |

```python
chunk_id = FIoChunkId(bytes=chunk_id_bytes)
chunk_id.id           # 64 位 ID
chunk_id.chunk_index  # Chunk 索引
chunk_id.chunk_group  # Chunk 组
chunk_id.chunk_type   # Chunk 类型
```

### FIoOffsetAndLength（10 字节）

IoStore 标准偏移/大小组合格式，10 字节大端编码：

| 字节范围 | 字段 | 说明 |
|----------|------|------|
| 0-4 | Offset (大端序) | 40 位偏移 |
| 5-9 | Length (大端序) | 40 位长度 |

```python
offset_length = FIoOffsetAndLength.from_bytes(data)  # 10 字节
offset_length.offset  # 偏移
offset_length.length  # 长度
```

### FIoOffsetAndSize（8 字节，旧版兼容）

40 位偏移 + 24 位大小，小端打包：

```python
packed = FIoOffsetAndSize(offset=xxx, size=xxx).pack()   # 8 字节
ofs = FIoOffsetAndSize.unpack(data)                       # 解包
```

## 枚举

### EIoStoreTocVersion（TOC 版本）

| 版本 | 名称 | 新增特性 |
|------|------|----------|
| 1 | Initial | 初始版本 |
| 2 | DirectoryIndex | 目录索引 |
| 3 | PartitionSize | 多分区支持 |
| 4 | PerfectHash | Perfect Hash 优化 |
| 5 | PerfectHashWithOverflow | Perfect Hash + 溢出处理 |
| 6 | OnDemandMetaData | 按需元数据 |
| 7 | RemovedOnDemandMetaData | 移除按需元数据 |
| 8 | ReplaceIoChunkHashWithIoHash | 使用 FIoHash 替代 FIoChunkHash |

### EIoChunkType（数据块类型）

| 类型值 | 名称 | 说明 | 最低版本 |
|--------|------|------|----------|
| 0 | Invalid | 无效 | — |
| 1 | ExportBundleData | 导出包数据 | UE5.0 |
| 2 | BulkData | 批量数据 | UE5.0 |
| 3 | OptionalBulkData | 可选批量数据 | UE5.0 |
| 4 | MemoryMappedBulkData | 内存映射批量数据 | UE5.0 |
| 5 | ScriptObjects | 脚本对象 | UE5.0 |
| 6 | ContainerHeader | 容器头部 | UE5.0 |
| 7 | ExternalFile | 外部文件引用 | UE5.1 |
| 8 | ShaderCodeLibrary | 着色器代码库 | UE5.1 |
| 9 | ShaderCode | 着色器代码 | UE5.1 |
| 10 | PackageStoreEntry | 包存储条目 | UE5.2 |
| 11 | DerivedData | 派生数据 | UE5.3 |
| 12 | EditorDerivedData | 编辑器派生数据 | UE5.4 |
| 13 | PackageResource | 包资源 | UE5.5 |

### EIoContainerFlags（容器标志）

| 标志 | 值 | 说明 |
|------|-----|------|
| None_ | 0 | 无标志 |
| Compressed | 1 << 0 | 容器使用压缩 |
| Encrypted | 1 << 1 | 容器使用加密 |
| Signed | 1 << 2 | 容器使用签名 |
| Indexed | 1 << 3 | 容器有目录索引 |
| OnDemand | 1 << 4 | 按需加载 |

## TOC 文件结构

`.utoc` 文件的完整布局（自顶向下读取）：

```
+───────────────────────────────────+
│ FIoStoreTocHeader (144 字节)      │  ← 魔数 + 版本 + 计数 + 标志
+───────────────────────────────────+
│ 对齐到 4 字节边界                 │
+───────────────────────────────────+
│ ChunkId 数组 (12 字节 × N)        │  ← N = toc_entry_count
+───────────────────────────────────+
│ OffsetAndLength 数组 (10 字节 × N)│
+───────────────────────────────────+
│ Perfect Hash 种子 (Version 4+)    │  ← 4 字节 × seed_count
+───────────────────────────────────+
│ 无 Perfect Hash 索引 (V5+)        │  ← 4 字节 × count
+───────────────────────────────────+
│ 压缩块条目 (12 字节 × M)          │  ← M = compressed_block_count
+───────────────────────────────────+
│ 压缩方法名 (name_count × length)  │  ← ASCII 定长字符串
+───────────────────────────────────+
│ 签名数据（如 Signed）             │  ← 可选，跳过
+───────────────────────────────────+
│ 目录索引缓冲区（如 Indexed）      │  ← 可变长度
+───────────────────────────────────+
```

### FIoStoreTocHeader（144 字节）

| 偏移 | 大小 | 字段 | 说明 |
|------|------|------|------|
| 0 | 16 | toc_magic | 魔数 `-==--==--==--==-` |
| 16 | 1 | version | TOC 版本（EIoStoreTocVersion） |
| 17 | 1 | reserved0 | 保留 |
| 18 | 2 | reserved1 | 保留 |
| 20 | 4 | toc_header_size | 头部大小 |
| 24 | 4 | toc_entry_count | Chunk 条目数 |
| 28 | 4 | toc_compressed_block_entry_count | 压缩块数 |
| 32 | 4 | toc_compressed_block_entry_size | 压缩块大小 |
| 36 | 4 | compression_method_name_count | 压缩方法名数量 |
| 40 | 4 | compression_method_name_length | 压缩方法名长度 |
| 44 | 4 | compression_block_size | 压缩块大小（字节） |
| 48 | 4 | directory_index_size | 目录索引大小 |
| 52 | 4 | partition_count | 分区数 |
| 64 | 8 | container_id (FIoContainerId) | 容器 ID |
| 72 | 16 | encryption_key_guid (FGuid) | 加密密钥 GUID |
| 88 | 4 | container_flags (EIoContainerFlags) | 容器标志 |
| 92 | 4 | toc_chunk_perfect_hash_seeds_count | Perfect Hash 种子数 |
| 96 | 8 | partition_size | 分区大小 |
| 104 | 4 | toc_chunks_without_perfect_hash_count | 无 Perfect Hash 的 Chunk 数 |

> [!NOTE]
> Version 3 之前无分区支持，partition_count 强制为 1，partition_size 为 ulong.MaxValue。

### FIoStoreTocCompressedBlockEntry（12 字节）

| 字节 | 字段 | 说明 |
|------|------|------|
| 0-4 | Offset (5 字节 LE) | 偏移 |
| 5-7 | CompressedSize (3 字节) | 压缩大小 |
| 8-10 | UncompressedSize (3 字节) | 解压大小 |
| 11 | CompressionMethodIndex (1 字节) | 压缩方法索引 |

## 目录索引

当容器带有 `Indexed` 标志时，`.utoc` 末尾包含目录索引缓冲区，支持按文件路径直接定位 Chunk。

### 索引结构

```
+───────────────────────────────────+
│ MountPoint (FString)              │  ← 挂载点路径
+───────────────────────────────────+
│ DirectoryEntries[] (FString 计数) │  ← 目录树
+───────────────────────────────────+
│ FileEntries[] (FString 计数)      │  ← 文件条目
+───────────────────────────────────+
│ StringTable[] (FString 计数)      │  ← 字符串池
+───────────────────────────────────+
```

### FIoDirectoryIndexEntry（16 字节）

| 偏移 | 字段 | 说明 |
|------|------|------|
| 0 | name | 名称索引（指向 StringTable） |
| 4 | first_child_entry | 首个子目录索引 |
| 8 | next_sibling_entry | 下一个兄弟目录索引 |
| 12 | first_file_entry | 首个文件条目索引 |

### FIoFileIndexEntry（12 字节）

| 偏移 | 字段 | 说明 |
|------|------|------|
| 0 | name | 文件名索引 |
| 4 | next_file_entry | 下一个文件条目索引 |
| 8 | user_data | Chunk 索引（指向 ChunkId 数组） |

> [!TIP]
> 目录索引使用递归树遍历：从根目录开始，先遍历文件条目，再递归子目录，最后移动到兄弟目录。

## Chunk 查找机制

### Perfect Hash（O(1)，Version 4+）

使用 64 位 FNV-1a 哈希算法 + 种子数组实现 O(1) 查找：

1. 根据种子索引找到种子值
2. 若种子为正：`slot = hash_with_seed(chunk_id, seed) % chunk_count`
3. 若种子为负：表示不完美哈希条目，转换为索引回退
4. 若种子为零：该位置无条目

```python
# FNV-1a 哈希（与 UE 源码一致）
hash_val = 0xcbf29ce484222325 ^ seed  # offset basis
for byte in chunk_id.bytes:
    hash_val ^= byte
    hash_val = (hash_val * 0x00000100000001B3) & 0xFFFFFFFFFFFFFFFF  # FNV prime
```

### 不完美哈希回退

Perfect Hash 无法覆盖的 Chunk 使用字典回退或线性搜索：

```python
# 方法 1：字典查找（预构建回退表）
self._toc_imperfect_hash_map.get(chunk_id)

# 方法 2：线性搜索
for i, cid in enumerate(self._chunk_ids):
    if cid == chunk_id:
        return self._chunk_offsets[i]
```

## 数据读取

### 无压缩直接读取

```python
reader.seek(partition_offset)
data = reader.read(length)
```

### 压缩块读取

1. 计算起始和结束压缩块索引
2. 逐块读取 → 解密（如加密）→ 解压
3. 从解压后的块中提取所需字节范围并拼接

支持的压缩方法由 TOC 中的压缩方法名指定（如 `LZ4`、`Zlib`、`Zstandard`）。

### 多分区读取

当 `partition_count > 1` 时：

- 分区文件命名：`game.ucas`、`game_s1.ucas`、`game_s2.ucas` ...
- 分区索引：`partition_index = offset // partition_size`
- 分区内偏移：`partition_offset = offset % partition_size`
- 支持跨分区连续读取

## 加密与签名

### 加密

当 `EIoContainerFlags.Encrypted` 设置时：

- 数据块使用 AES-ECB 解密
- 目录索引缓冲区使用 AES-ECB 解密
- 需要对齐到 16 字节边界
- 需提供 AES 密钥

### 签名

当 `EIoContainerFlags.Signed` 设置时：

- TOC 中包含 `tocSignature`、`blockSignature` 和每个压缩块的 FSHAHash
- 签名数据在解析时被跳过

## 与 PAK 格式对比

| 特性 | PAK | IoStore |
|------|-----|---------|
| 文件结构 | 单文件 | 双文件（.utoc + .ucas） |
| 查找方式 | 字典/线性 | Perfect Hash O(1) |
| 压缩粒度 | 按条目 | 按压缩块（可跨 Chunk 共享） |
| 多分区 | 不支持 | 支持 |
| 目录索引 | 无 | 有（支持按路径查找） |
| 版本 | UE4/UE5 | UE5.0+ |
