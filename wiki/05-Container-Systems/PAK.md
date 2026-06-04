---
title: PAK 文件读取
section: pak
---

# PAK 文件读取

PAK 模块提供对 Unreal Engine `.pak` 容器文件的完整解析能力，支持从 v1 到 v12 的所有文件格式，涵盖索引解密、bitfield 编码条目解析、多种压缩算法和 AES-ECB 加密。

**源码**: `src/uasset_read/pak/`

## 核心 API

### PakFileReader

```python
PakFileReader(path: str, aes_key: bytes | None = None, tolerant: bool = False)
  .open() -> None              # 打开文件并解析 FPakInfo + Primary Index
  .close() -> None             # 关闭文件句柄
  .list_files() -> list[str]   # 返回所有非删除条目的路径
  .get_entry(path: str) -> FPakEntry | None  # 获取条目信息
  .extract(path: str) -> bytes | None        # 提取并解压文件数据

# 上下文管理器
with PakFileReader("game.pak") as reader:
    info = reader.info           # FPakInfo
    files = reader.list_files()
    data = reader.extract("path/to/file.uasset")
```

### 模块公共 API

```python
# 常量
PAK_FILE_MAGIC                     # 0x5A6F12E1
PakFileVersion                       # v1~v12 版本枚举
ECompressionFlags                   # 压缩标志（v8 前使用）
Flag_Encrypted, Flag_Deleted         # 条目标志

# 数据结构
FPakInfo                            # PAK 尾部信息（版本、索引偏移、加密 GUID）
FPakEntry                           # 文件条目（偏移、大小、压缩块、哈希）
FPakDirectoryEntry                  # 目录条目（路径 + 文件名 + 条目数据）
FPakCompressedBlock                 # 压缩块（起始/结束偏移）
read_fstream(stream, version)       # FString 反序列化

# 索引解析
parse_primary_index(stream, pak_info, aes_key) -> (mount_point, entries, extra)
parse_path_hash_index(file_stream, offset, size, pak_info) -> dict
parse_directory_index(file_stream, offset, size, pak_info) -> dict

# 压缩
decompress_block(data, uncompressed_size, method) -> bytes
decompress_entry(stream, entry, compression_method, encryption_key) -> bytes

# 加密
decrypt_aes_ecb(data, key) -> bytes
validate_index_hash(decrypted_blob, expected_hash) -> bool
decrypt_index_blob(index_data, key, expected_hash) -> bytes

# 游戏检测
detect_game_from_magic(magic) -> EGame
get_game_info(game) -> (name, version)
```

## 文件结构

### 模块文件

| 文件 | 职责 |
|------|------|
| `pak/__init__.py` | 公共 API 导出 |
| `pak/constants.py` | 魔数、版本枚举、标志位、大小常量 |
| `pak/structures.py` | FPakInfo、FPakEntry、FPakDirectoryEntry 数据结构 + FString 读取 |
| `pak/reader.py` | PakFileReader 主读取器（上下文管理器、条目解析、解压缩调度） |
| `pak/index.py` | Primary Index 解析（legacy v<10 和 v10+ PathHashIndex） |
| `pak/decompress.py` | 压缩块解压缩调度（Zlib/Gzip/LZ4/Zstd/Oodle） |
| `pak/crypto.py` | AES-ECB 解密、索引哈希验证 |
| `pak/game_versions.py` | 游戏标识检测（魔数 → 游戏 → PAK 版本映射） |

### 二进制布局

```
┌─────────────────────────────────────────────────────┐
│                     .pak 文件                         │
├─────────────────────────────────────────────────────┤
│  Mount Point (FString)                              │
│  Index Blob (Primary Index)                          │
│    ├─ v<10: N × (FString path + FPakEntry)           │
│    └─ v10+: PathHashSeed + PathHashIndex             │
│             + DirectoryIndex + Encoded Entries        │
│  ... 文件数据区域 ...                                 │
├─────────────────────────────────────────────────────┤
│  FPakInfo Trailer（文件尾部）                          │
│    ├─ v<7: Magic(4) + Version(4) + IndexOffset(8)    │
│    │         + IndexSize(8) + IndexHash(20)          │
│    ├─ v7:  + EncryptionKeyGuid(16) + bEncrypted(1)   │
│    ├─ v8:  + CompressionMethods(32×5)               │
│    └─ v9:  + FrozenIndex(1)                          │
│    └─ v10+: - FrozenIndex（移除）                     │
└─────────────────────────────────────────────────────┘
```

## 数据结构

### FPakInfo

PAK 文件尾部信息结构，位于文件末尾，通过从尾部反向扫描检测。

```python
@dataclass
class FPakInfo:
    magic: int                      # 魔数（标准或游戏特定）
    version: int                    # 文件格式版本 (1~12)
    index_offset: int               # Primary Index 在文件中的偏移
    index_size: int                 # Index blob 大小
    index_hash: bytes               # SHA1 of index blob (20 bytes)
    encryption_key_guid: bytes      # 加密密钥 GUID (16 bytes, v7+)
    encrypted_index: bool           # 索引是否加密 (v7+)
    compression_methods: list       # 压缩方法名称表 (最多 5 个, v8+)
    index_is_frozen: bool           # FrozenIndex 标志 (v9 only)
    detected_game: int              # 检测到的游戏标识
```

**各版本序列化大小**:

| 版本范围 | 大小 | 字段 |
|----------|------|------|
| v1~6 | 44 bytes | Magic + Version + IndexOffset + IndexSize + IndexHash |
| v7 | 61 bytes | + EncryptionKeyGuid(16) + bEncryptedIndex(1) |
| v8 | 221 bytes | + CompressionMethods(32×5=160) |
| v9 | 222 bytes | + FrozenIndex(1) |
| v10+ | 221 bytes | - FrozenIndex（移除） |

### FPakEntry

描述 PAK 中单个文件的偏移、大小、压缩、加密和哈希信息。

```python
@dataclass
class FPakEntry:
    offset: int                     # 条目数据起始偏移 (int64)
    uncompressed_size: int          # 解压后大小 (int64)
    size: int                       # 压缩大小 (int64, 未压缩时 == uncompressed_size)
    compression_method_index: int   # 在 FPakInfo.compression_methods 中的索引 (uint32)
    is_encrypted: bool              # 是否加密
    is_compressed: bool             # 是否压缩 (derived)
    compression_block_count: int    # 压缩块数量
    compression_block_size: int     # 每个压缩块的大小 (uint32)
    compression_blocks: list        # list[FPakCompressedBlock]
    hash: bytes                     # SHA1 of uncompressed data (20 bytes)
    flags: int                      # 原始标志位
    is_deleted: bool                # 是否已删除 (derived from flags)
    serialized_size: int            # v10+ bitfield 编码时的条目大小
```

**v10+ Bitfield 编码布局**:

| 位 | 字段 | 说明 |
|----|------|------|
| 31 | Offset fits 32-bit | 为 1 时 Offset 用 uint32 存储 |
| 30 | UncompressedSize fits 32-bit | 为 1 时用 uint32 |
| 29 | Size fits 32-bit | 为 1 时用 uint32 |
| 23~28 | Compression method index | 6 位，索引值 |
| 22 | Encrypted flag | 1 位 |
| 6~21 | Compression block count | 16 位 |
| 0~5 | Compression block size index | 6 位，0x3F 表示从流中读取 |

### FPakCompressedBlock

```python
@dataclass
class FPakCompressedBlock:
    compressed_start: int     # 绝对文件偏移 (int64)
    compressed_end: int       # 独占结束偏移 (int64)
```

### FPakDirectoryEntry

```python
@dataclass
class FPakDirectoryEntry:
    path: str             # 目录路径
    filename: str         # 文件名
    entry: FPakEntry      # 条目数据
```

## 文件版本

```
v1   Initial — 初始版本
v2   NoTimestamps — 移除 FPakEntry 中的 Timestamp 字段
v3   CompressionEncryption — 压缩加密支持（旧格式）
v4   IndexEncryption — 索引加密支持（旧格式）
v5   RelativeChunkOffsets — 压缩块偏移改为相对值
v6   DeleteRecords — 添加 Flag_Deleted 支持
v7   EncryptionKeyGuid — 添加 EncryptionKeyGuid 和 bEncryptedIndex
v8   FNameBasedCompressionMethod — 添加 CompressionMethods 名称表（替代位标志）
v9   FrozenIndex — 添加 FrozenIndex 标志（已废弃）
v10  PathHashIndex — 引入 PathHashIndex、DirectoryIndex、bitfield 编码条目
v11  Fnv64BugFix — FNV64 哈希碰撞修复（Frostbite 游戏特定）
v12  Utf8PakDirectory — 目录名称使用 FUtf8String（uint32 长度 + UTF-8）
```

## 压缩与加密

### 压缩方法

| 方法 | 说明 | 依赖 |
|------|------|------|
| None | 无压缩 | 无 |
| Zlib | raw deflate (wbits=-15) | 无（stdlib） |
| Gzip | gzip 格式 | 无（stdlib） |
| LZ4 | LZ4 块压缩 | `lz4`（可选） |
| Zstd | Zstandard 压缩 | `zstandard`（可选） |
| Oodle | Oodle 压缩（专有） | `oo2core`（不支持） |

**压缩方法映射**:

| 索引 | 名称 |
|------|------|
| 0 | None |
| 1 | Zlib |
| 2 | Gzip |
| 3 | Oodle |
| 4 | LZ4 |
| 5 | Zstd |

### AES 加密

- **算法**: AES-ECB（无填充）
- **密钥长度**: 16 bytes（128-bit）
- **对齐**: 16 字节对齐
- **依赖**: `cryptography`（可选）
- **应用范围**: 文件条目数据 + 索引 blob（v7+）

### 魔数

标准魔数: `0x5A6F12E1`

游戏特定魔数:

| 魔数 | 游戏 | 对应 PAK 版本 |
|------|------|---------------|
| `0x5A6F12E1` | Standard (默认) | v12 |
| `0xA590ED1E` | Outlast Trials | v10 |
| `0x6B2A56B8` | Torchlight Infinite | v10 |
| `0xA4CCD123` | Wild Assault | v10 |
| `0x5A6F12EC` | Gameloop Undawn | v10 |
| `0x65617441` | Friday the 13th | v5 |
| `0x1B6A32F1` | Dream Star | v10 |
| `0xFF67FF70` | Game for Peace | v8 |
| `0x81C4B35B` | KartRider Drift | v10 |
| `0x9A51DA3F` | Racing Master | v10 |
| `0x22CE976A` | Crystal of Atlan | v10 |
| `0x11ADDE11` | Promise Mascot Agency | v10 |
| `0x53647586` | Arena Breakout Infinite | v10 |
| `0x4F6FAE86` | Assault Fire Future | v10 |

## 索引格式

### Legacy 格式（v<10）

```
Mount Point (FString)
Entry Count (int32)
├─ 对于每个条目:
│  ├─ Path (FString)
│  └─ FPakEntry (legacy 反序列化)
```

### v10+ 格式

```
Mount Point (FString)
Entry Count (int32)
PathHashSeed (uint64)
bHasPathHashIndex (bool)
├─ 如果为 true:
│  ├─ PathHashIndexOffset (int64)
│  └─ PathHashIndexSize (int64)
bHasDirectoryIndex (bool)
├─ 如果为 true:
│  ├─ DirectoryIndexOffset (int64)
│  └─ DirectoryIndexSize (int64)
EncodedPakEntries: Count (uint32) + N × (serialized_size + bitfield data)
NonEncodedEntries: Count (uint32) + N × (FString path + serialized_size + bitfield data)
```

### PathHashIndex

```
Entry Count (uint32)
├─ 对于每个条目:
│  ├─ PathHash (uint64)
│  ├─ FileOffset (int64)
│  └─ EntrySize (int64)
```

映射: `path_hash -> (file_offset, size)`

### DirectoryIndex

```
Directory Count (uint32)
├─ 对于每个目录:
│  ├─ DirName (FString)
│  ├─ File Count (uint32)
│  └─ 对于每个文件:
│     ├─ FileName (FString)
│     ├─ FileOffset (int64)
│     └─ FileSize (int64)
```

映射: `directory -> {filename -> (file_offset, size)}`

## FString 读取

UE FString 格式（带长度前缀，null-terminated）:

| 长度值 | 编码 | 数据长度 | 终止符 |
|--------|------|----------|--------|
| 0 | 空字符串 | — | — |
| >0 | ANSI/UTF-8 | length 字节 | 1 字节 `\x00` |
| <0 | UTF-16LE | abs(length) × 2 字节 | 2 字节 `\x00\x00` |
| v12+ uint32 | UTF-8 | length 字节 | 1 字节 `\x00` |

**安全限制**: 字符串长度不超过 `MAX_FSTRING_LENGTH`。

## 使用示例

### 基本读取

```python
from uasset_read.pak import PakFileReader

with PakFileReader("game.pak") as reader:
    # 查看 PAK 信息
    print(f"Version: {reader.info.version}")
    print(f"Mount point: {reader.mount_point}")
    print(f"Entries: {len(reader.entries)}")

    # 列出所有文件
    for path in reader.list_files():
        print(path)

    # 提取文件
    data = reader.extract("Game/Content/MyBlueprint.uasset")
    if data:
        with open("MyBlueprint.uasset", "wb") as f:
            f.write(data)
```

### 加密 PAK 读取

```python
aes_key = bytes.fromhex("0123456789abcdef0123456789abcdef")

with PakFileReader("encrypted.pak", aes_key=aes_key) as reader:
    if reader.info.encrypted_index:
        print("Index is encrypted")
        print(f"Encryption Key GUID: {reader.info.encryption_key_guid.hex()}")

    data = reader.extract("Game/Content/EncryptedAsset.uasset")
```

### 手动解析 FPakInfo

```python
from uasset_read.pak import FPakInfo

with open("game.pak", "rb") as f:
    f.seek(0, 2)
    file_size = f.tell()
    f.seek(0)

    info = FPakInfo.deserialize(f, file_size)
    print(f"Magic: 0x{info.magic:08X}")
    print(f"Version: {info.version}")
    print(f"Game: {info.detected_game}")
    print(f"Index offset: {info.index_offset}")
    print(f"Methods: {info.compression_methods}")
```

## 依赖

| 功能 | 包 | 必需 |
|------|------|------|
| 基本解析 | Python stdlib | 是 |
| LZ4 解压 | `lz4` | 可选 |
| Zstd 解压 | `zstandard` | 可选 |
| AES 解密 | `cryptography` | 可选 |
| Oodle 解压 | `oo2core` | 不支持（专有） |

## 相关章节

[[包管理]] · [[IoStore 容器]] · [[原始文件解析]]
