"""
Pak 文件 Primary Index 解析模块

处理 legacy (v<10) 和 v10+ (PathHashIndex + bitfield 编码) 两种索引格式。
"""
import struct
import logging
from io import BytesIO
from typing import BinaryIO

from uasset_read.exceptions import ParseError
from uasset_read.pak.constants import PakFileVersion
from uasset_read.pak.structures import FPakInfo, FPakEntry, FPakDirectoryEntry, read_fstring

logger = logging.getLogger(__name__)


def parse_primary_index(
    stream: BinaryIO,
    pak_info: FPakInfo,
    aes_key: bytes | None = None,
) -> tuple[str, dict[str, FPakEntry], dict]:
    """解析 Primary Index blob。

    Args:
        stream: 文件流（已打开）
        pak_info: 已解析的 FPakInfo
        aes_key: AES 密钥（加密索引时需要）

    Returns:
        (mount_point, entries_dict, extra_info)
        - mount_point: 挂载点路径
        - entries_dict: path -> FPakEntry 映射
        - extra_info: 附加信息（path_hash_index, directory_index 等）

    Raises:
        ParseError: 哈希验证失败或索引格式错误
        ImportError: 需要 AES 密钥但缺少 cryptography 包
    """
    from uasset_read.pak.crypto import decrypt_index_blob, validate_index_hash

    # Step 1: Read index blob
    stream.seek(pak_info.index_offset)
    index_blob = stream.read(pak_info.index_size)
    if len(index_blob) != pak_info.index_size:
        raise ParseError(
            f"Index blob truncated: expected {pak_info.index_size}, got {len(index_blob)}"
        )

    # Step 2: Decrypt or validate
    if pak_info.encrypted_index:
        if aes_key is None:
            raise ParseError("Encrypted index requires AES key")
        index_blob = decrypt_index_blob(index_blob, aes_key, pak_info.index_hash)
    else:
        if not validate_index_hash(index_blob, pak_info.index_hash):
            raise ParseError("Index hash mismatch — index blob is corrupted")

    index_stream = BytesIO(index_blob)

    # Step 3: Read mount point
    mount_point = read_fstring(index_stream, pak_info.version)

    # Step 4: Read number of entries
    num_entries_bytes = index_stream.read(4)
    if len(num_entries_bytes) < 4:
        raise ParseError("Unexpected end of index: cannot read entry count")
    num_entries = struct.unpack('<i', num_entries_bytes)[0]

    if num_entries < 0:
        raise ParseError(f"Invalid entry count: {num_entries}")

    # Step 5: Branch by version
    if pak_info.version < PakFileVersion.PathHashIndex:
        # Legacy format (v<10): flat list of (path, FPakEntry)
        entries = _parse_legacy_index(index_stream, num_entries, pak_info.version)
        return mount_point, entries, {}
    else:
        # v10+ format: PathHashIndex + bitfield entries
        return _parse_v10_index(index_stream, stream, num_entries, pak_info, mount_point)


def _parse_legacy_index(
    stream: BytesIO,
    num_entries: int,
    version: int,
) -> dict[str, FPakEntry]:
    """解析 legacy 格式索引（v<10）：mount_point + N 个 (path, FPakEntry) 对。"""
    entries: dict[str, FPakEntry] = {}

    for _ in range(num_entries):
        path = read_fstring(stream, version)
        if not path:
            raise ParseError("Empty path in legacy index")

        entry = FPakEntry.deserialize_legacy(stream, version)
        entries[path] = entry

    logger.debug("Parsed %d legacy entries", len(entries))
    return entries


def _parse_v10_index(
    index_stream: BytesIO,
    file_stream: BinaryIO,
    num_entries: int,
    pak_info: FPakInfo,
    mount_point: str,
) -> tuple[str, dict[str, FPakEntry], dict]:
    """解析 v10+ 格式索引：PathHashSeed + PathHashIndex + DirectoryIndex + 编码条目。

    序列化顺序（UE PakFile.cpp LoadIndex）：
    1. PathHashSeed (uint64)
    2. bHasPathHashIndex (bool)
    3. If true: PathHashIndexOffset (int64) + PathHashIndexSize (int64)
    4. bHasDirectoryIndex (bool)
    5. If true: DirectoryIndexOffset (int64) + DirectoryIndexSize (int64)
    6. EncodedPakEntries: count (uint32) + bitfield entries
    7. NonEncodedEntries: count (uint32) + (FString path + bitfield entry) pairs
    """
    # Read PathHashSeed
    seed_bytes = index_stream.read(8)
    if len(seed_bytes) < 8:
        raise ParseError("Unexpected end of index: cannot read PathHashSeed")
    path_hash_seed = struct.unpack('<Q', seed_bytes)[0]

    # Read bHasPathHashIndex
    b_has_path_hash = index_stream.read(1)[0] != 0

    path_hash_index: dict[int, tuple[int, int]] = {}
    if b_has_path_hash:
        ph_offset = struct.unpack('<q', index_stream.read(8))[0]
        ph_size = struct.unpack('<q', index_stream.read(8))[0]
        if ph_size > 0:
            path_hash_index = parse_path_hash_index(file_stream, ph_offset, ph_size, pak_info)

    # Read bHasDirectoryIndex
    b_has_directory = index_stream.read(1)[0] != 0

    directory_index: dict[str, dict[str, tuple[int, int]]] = {}
    if b_has_directory:
        di_offset = struct.unpack('<q', index_stream.read(8))[0]
        di_size = struct.unpack('<q', index_stream.read(8))[0]
        if di_size > 0:
            directory_index = parse_directory_index(file_stream, di_offset, di_size, pak_info)

    # Read EncodedPakEntries (bitfield-encoded, no explicit path)
    num_encoded = struct.unpack('<I', index_stream.read(4))[0]
    encoded_entries: list[FPakEntry] = []
    for _ in range(num_encoded):
        # Read serialized size first, then the bitfield data
        serialized_size = struct.unpack('<I', index_stream.read(4))[0]
        entry_data = index_stream.read(serialized_size)
        if len(entry_data) < serialized_size:
            raise ParseError(
                f"Encoded entry truncated: expected {serialized_size} bytes"
            )
        entry, _ = FPakEntry.decode_bitfield(entry_data, 0, pak_info)
        encoded_entries.append(entry)

    # Read NonEncodedEntries (FString path + bitfield)
    num_non_encoded = struct.unpack('<I', index_stream.read(4))[0]
    entries: dict[str, FPakEntry] = {}
    for _ in range(num_non_encoded):
        path = read_fstring(index_stream, pak_info.version)
        serialized_size = struct.unpack('<I', index_stream.read(4))[0]
        entry_data = index_stream.read(serialized_size)
        if len(entry_data) < serialized_size:
            raise ParseError(
                f"Non-encoded entry truncated: expected {serialized_size} bytes"
            )
        entry, _ = FPakEntry.decode_bitfield(entry_data, 0, pak_info)
        entries[path] = entry

    # Merge encoded entries (keyed by path hash for lookup later)
    extra_info = {
        "path_hash_seed": path_hash_seed,
        "path_hash_index": path_hash_index,
        "directory_index": directory_index,
        "encoded_entries": encoded_entries,
    }

    total = len(entries) + len(encoded_entries)
    logger.debug("Parsed v10+ index: %d named + %d encoded = %d total entries",
                 len(entries), len(encoded_entries), total)

    return mount_point, entries, extra_info




def parse_path_hash_index(
    file_stream: BinaryIO,
    offset: int,
    size: int,
    pak_info: FPakInfo,
) -> dict[int, tuple[int, int]]:
    """解析 PathHashIndex（v10+）。

    TMap<uint64 path_hash, FPakEntryLocation>:
    - num_entries (uint32)
    - For each: key=uint64 (hash), value=file_offset(int64) + size(int64)

    Args:
        file_stream: 文件流
        offset: PathHashIndex 在文件中的偏移
        size: PathHashIndex 的大小
        pak_info: FPakInfo 实例

    Returns:
        dict mapping path_hash -> (file_offset, size)
    """
    file_stream.seek(offset)
    data = file_stream.read(size)
    if len(data) != size:
        raise ParseError(
            f"PathHashIndex truncated: expected {size}, got {len(data)}"
        )

    stream = BytesIO(data)
    num_entries = struct.unpack('<I', stream.read(4))[0]

    result: dict[int, tuple[int, int]] = {}
    for _ in range(num_entries):
        path_hash = struct.unpack('<Q', stream.read(8))[0]
        file_offset = struct.unpack('<q', stream.read(8))[0]
        entry_size = struct.unpack('<q', stream.read(8))[0]
        result[path_hash] = (file_offset, entry_size)

    logger.debug("Parsed PathHashIndex: %d entries", len(result))
    return result


def parse_directory_index(
    file_stream: BinaryIO,
    offset: int,
    size: int,
    pak_info: FPakInfo,
) -> dict[str, dict[str, tuple[int, int]]]:
    """解析 DirectoryIndex（v10+）。

    TMap<FString directory, TMap<FString filename, FPakEntryLocation>>:
    - num_directories (uint32)
    - For each directory: dir_name(FString), num_files(uint32)
    - For each file: file_name(FString), file_offset(int64), file_size(int64)

    Args:
        file_stream: 文件流
        offset: DirectoryIndex 在文件中的偏移
        size: DirectoryIndex 的大小
        pak_info: FPakInfo 实例

    Returns:
        Nested dict: directory -> {filename -> (file_offset, size)}
    """
    file_stream.seek(offset)
    data = file_stream.read(size)
    if len(data) != size:
        raise ParseError(
            f"DirectoryIndex truncated: expected {size}, got {len(data)}"
        )

    stream = BytesIO(data)
    num_dirs = struct.unpack('<I', stream.read(4))[0]

    result: dict[str, dict[str, tuple[int, int]]] = {}
    for _ in range(num_dirs):
        dir_name = read_fstring(stream, pak_info.version)
        num_files = struct.unpack('<I', stream.read(4))[0]

        files: dict[str, tuple[int, int]] = {}
        for _ in range(num_files):
            file_name = read_fstring(stream, pak_info.version)
            file_offset = struct.unpack('<q', stream.read(8))[0]
            file_size = struct.unpack('<q', stream.read(8))[0]
            files[file_name] = (file_offset, file_size)

        result[dir_name] = files

    logger.debug("Parsed DirectoryIndex: %d directories", len(result))
    return result
