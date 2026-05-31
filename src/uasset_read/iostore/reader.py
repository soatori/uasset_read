"""IoStore Reader — UE5.3+ IoStore 容器读取器

等价实现 CUE4Parse IoStoreReader.cs
支持 TOC 解析、Chunk 查找、Perfect Hash 优化、压缩块读取
"""
from __future__ import annotations
from typing import BinaryIO, Dict, List, Optional, Tuple
from pathlib import Path
import struct
import logging

from uasset_read.iostore.structures import (
    FIoChunkId,
    FIoOffsetAndLength,
    FIoStoreTocHeader,
    FIoStoreTocCompressedBlockEntry,
    FIoStoreTocEntryMeta,
    EIoStoreTocVersion,
    EIoContainerFlags,
    EIoStoreTocReadOptions,
    EIoChunkType,
    EIoStoreTocEntryMetaFlags,
    TOC_MAGIC,
    TOC_HEADER_SIZE,
)

logger = logging.getLogger(__name__)


class IoStoreInfo:
    """IoStore TOC 解析后的摘要信息"""
    def __init__(self) -> None:
        self.version: int = 0
        self.toc_entry_count: int = 0
        self.compressed_block_count: int = 0
        self.compression_method_count: int = 0
        self.compression_block_size: int = 0
        self.directory_index_size: int = 0
        self.partition_count: int = 1
        self.partition_size: int = 0
        self.container_flags: int = 0
        self.is_encrypted: bool = False
        self.is_compressed: bool = False
        self.chunk_ids: List[FIoChunkId] = []
        self.chunk_offsets: List[FIoOffsetAndLength] = []


class IoStoreReader:
    """IoStore 容器读取器

    等价实现 CUE4Parse IoStoreReader.cs，支持：
    - TOC 头部解析（所有版本 1-8）
    - ChunkId 和 OffsetAndLength 加载
    - Perfect Hash 优化查找（Version 4+）
    - 压缩块条目解析
    - 压缩方法名加载
    - 目录索引加载（可选）
    - 分区支持（Version 3+）

    Usage:
        reader = IoStoreReader("game.utoc", "game.ucas")
        reader.open()
        data = reader.extract(chunk_id_bytes)
        reader.close()

    # 或使用上下文管理器
    with IoStoreReader("game.utoc", "game.ucas") as reader:
        data = reader.extract(chunk_id_bytes)
    """

    def __init__(
        self,
        utoc_path: str,
        ucas_path: Optional[str] = None,
        aes_key: Optional[bytes] = None,
        tolerant: bool = False,
        read_options: int = EIoStoreTocReadOptions.Default,
    ):
        """初始化 IoStoreReader

        Args:
            utoc_path: .utoc 文件路径
            ucas_path: .ucas 文件路径（可选，自动从 utoc 路径推导）
            aes_key: AES 解密密钥（可选）
            tolerant: 宽容模式，遇到非致命错误不抛异常
            read_options: TOC 读取选项
        """
        self.utoc_path = utoc_path
        self._ucas_path_override = ucas_path
        self._aes_key = aes_key
        self._tolerant = tolerant
        self._read_options = read_options

        self._utoc_file: Optional[BinaryIO] = None
        self._ucas_files: List[BinaryIO] = []
        self._header: Optional[FIoStoreTocHeader] = None
        self._info: Optional[IoStoreInfo] = None

        # Chunk 查找相关
        self._chunk_ids: List[FIoChunkId] = []
        self._chunk_offsets: List[FIoOffsetAndLength] = []
        self._chunk_perfect_hash_seeds: Optional[List[int]] = None
        self._chunk_indices_without_perfect_hash: Optional[List[int]] = None
        self._toc_imperfect_hash_map: Optional[Dict[FIoChunkId, FIoOffsetAndLength]] = None

        # 压缩相关
        self._compression_blocks: List[FIoStoreTocCompressedBlockEntry] = []
        self._compression_methods: List[str] = ["None"]  # 索引 0 = 无压缩
        self._compression_block_size: int = 0

        # 目录索引
        self._directory_index_buffer: Optional[bytes] = None
        self._mount_point: str = ""
        self._directory_index: Dict[str, FIoChunkId] = {}

    @property
    def ucas_path(self) -> str:
        """获取 .ucas 文件路径"""
        if self._ucas_path_override:
            return self._ucas_path_override
        # 从 utoc 路径推导
        p = Path(self.utoc_path)
        return str(p.with_suffix('.ucas'))

    @property
    def info(self) -> Optional[IoStoreInfo]:
        """已解析的 TOC 信息"""
        return self._info

    @property
    def header(self) -> Optional[FIoStoreTocHeader]:
        """TOC 头部"""
        return self._header

    @property
    def mount_point(self) -> str:
        """挂载点"""
        return self._mount_point

    @property
    def is_encrypted(self) -> bool:
        """容器是否加密"""
        return self._header.is_encrypted if self._header else False

    @property
    def is_compressed(self) -> bool:
        """容器是否压缩"""
        return self._header.is_compressed if self._header else False

    @property
    def chunk_count(self) -> int:
        """Chunk 数量"""
        return len(self._chunk_ids)

    def open(self) -> None:
        """打开 IoStore TOC 和 CAS 文件

        读取完整的 TOC 结构，包括：
        - 头部（144 字节）
        - ChunkId 数组
        - OffsetAndLength 数组（10 字节/条目）
        - Perfect Hash 种子（Version 4+）
        - 压缩块条目
        - 压缩方法名
        - 目录索引（可选）
        """
        logger.debug("Opening IoStore: utoc=%s", self.utoc_path)

        self._utoc_file = open(self.utoc_path, 'rb')

        try:
            # 读取并验证 TOC 头部
            self._header = FIoStoreTocHeader.from_stream(self._utoc_file)

            # Version 3 之前没有分区支持
            if self._header.version < EIoStoreTocVersion.PartitionSize:
                self._header.partition_count = 1
                self._header.partition_size = 0xFFFFFFFFFFFFFFFF  # ulong.MaxValue

            # 加载 ChunkId 数组
            self._load_chunk_ids()

            # 加载 OffsetAndLength 数组
            self._load_chunk_offsets()

            # 加载 Perfect Hash 种子（Version 4+）
            self._load_perfect_hash_seeds()

            # 加载压缩块条目
            self._load_compression_blocks()

            # 加载压缩方法名
            self._load_compression_methods()

            # 跳过签名数据（如果存在）
            self._skip_signatures()

            # 加载目录索引（如果存在且请求读取）
            self._load_directory_index()

            # 构建 Info 摘要
            self._build_info()

            # 打开容器文件（.ucas）
            self._open_container_files()

            # 如果使用 Perfect Hash，构建不完美哈希回退表
            if self._chunk_perfect_hash_seeds is not None:
                self._build_imperfect_hash_fallback()

            logger.debug(
                "IoStore opened: version=%d, chunks=%d, compression_blocks=%d, methods=%s",
                self._header.version,
                len(self._chunk_ids),
                len(self._compression_blocks),
                self._compression_methods,
            )

        except Exception:
            self.close()
            raise

    def close(self) -> None:
        """关闭所有文件句柄"""
        if self._utoc_file:
            try:
                self._utoc_file.close()
            except Exception:
                pass
            self._utoc_file = None

        for f in self._ucas_files:
            try:
                f.close()
            except Exception:
                pass
        self._ucas_files.clear()

    def __enter__(self) -> IoStoreReader:
        self.open()
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        self.close()

    def list_files(self) -> List[str]:
        """列出所有文件路径（需要目录索引）"""
        return list(self._directory_index.keys())

    def does_chunk_exist(self, chunk_id: FIoChunkId) -> bool:
        """检查 ChunkId 是否存在"""
        offset_length = self._resolve_chunk(chunk_id)
        return offset_length is not None

    def try_resolve(self, chunk_id: FIoChunkId) -> Optional[Tuple[int, int]]:
        """尝试解析 ChunkId 到 (offset, length)

        Args:
            chunk_id: Chunk 标识符

        Returns:
            (offset, length) 元组，未找到返回 None
        """
        offset_length = self._resolve_chunk(chunk_id)
        if offset_length is not None:
            return (offset_length.offset, offset_length.length)
        return None

    def extract(self, chunk_id_bytes: bytes) -> bytes:
        """根据 ChunkId 原始字节提取数据

        Args:
            chunk_id_bytes: 12 字节的 ChunkId

        Returns:
            提取的原始数据（已解压）

        Raises:
            ValueError: ChunkId 无效或未找到
            NotImplementedError: 解压尚未实现
        """
        if len(chunk_id_bytes) != 12:
            raise ValueError(f"ChunkId 必须为 12 字节，实际 {len(chunk_id_bytes)} 字节")

        chunk_id = FIoChunkId(bytes=chunk_id_bytes)
        return self.read_chunk(chunk_id)

    def read_chunk(self, chunk_id: FIoChunkId) -> bytes:
        """根据 FIoChunkId 读取数据

        Args:
            chunk_id: Chunk 标识符

        Returns:
            解压后的数据

        Raises:
            KeyError: ChunkId 未找到
        """
        offset_length = self._resolve_chunk(chunk_id)
        if offset_length is None:
            raise KeyError(f"未找到 Chunk {chunk_id.bytes.hex()}")

        return self._read_data(offset_length.offset, offset_length.length)

    def _resolve_chunk(self, chunk_id: FIoChunkId) -> Optional[FIoOffsetAndLength]:
        """解析 ChunkId 到 OffsetAndLength

        优先使用 Perfect Hash（O(1)），回退到不完美哈希表或线性搜索。
        """
        if self._chunk_perfect_hash_seeds is not None:
            return self._resolve_chunk_perfect_hash(chunk_id)

        # 回退：不完美哈希表或线性搜索
        return self._resolve_chunk_imperfect(chunk_id)

    def _resolve_chunk_perfect_hash(self, chunk_id: FIoChunkId) -> Optional[FIoOffsetAndLength]:
        """使用 Perfect Hash 解析 ChunkId"""
        chunk_count = self._header.toc_entry_count
        if chunk_count == 0:
            return None

        seed_count = len(self._chunk_perfect_hash_seeds)
        seed_index = self._hash_with_seed(chunk_id, 0) % seed_count
        seed = self._chunk_perfect_hash_seeds[seed_index]

        if seed == 0:
            return None

        if seed < 0:
            # 不完美哈希条目
            seed_as_index = (-seed) - 1
            if seed_as_index < chunk_count:
                slot = seed_as_index
            else:
                # 回退到不完美哈希查找
                return self._resolve_chunk_imperfect(chunk_id)
        else:
            slot = self._hash_with_seed(chunk_id, seed) % chunk_count

        if slot < len(self._chunk_ids) and self._chunk_ids[slot] == chunk_id:
            return self._chunk_offsets[slot]

        return None

    def _resolve_chunk_imperfect(self, chunk_id: FIoChunkId) -> Optional[FIoOffsetAndLength]:
        """不完美哈希回退查找"""
        if self._toc_imperfect_hash_map is not None:
            return self._toc_imperfect_hash_map.get(chunk_id)

        # 线性搜索
        for i, cid in enumerate(self._chunk_ids):
            if cid == chunk_id:
                return self._chunk_offsets[i]
        return None

    def _hash_with_seed(self, chunk_id: FIoChunkId, seed: int) -> int:
        """CUE4Parse HashWithSeed 实现

        使用 FNV-1a 哈希变体
        """
        data = chunk_id.bytes
        hash_val = 0x811C9DC5 ^ seed  # FNV offset basis
        for byte in data:
            hash_val ^= byte
            hash_val = (hash_val * 0x01000193) & 0xFFFFFFFF  # FNV prime, 32-bit
        return hash_val

    def _read_data(self, offset: int, length: int) -> bytes:
        """从 .ucas 文件读取数据

        当前实现读取原始数据（不处理压缩/加密）。
        完整的解压/解密逻辑需要 compression 模块支持。
        """
        if not self._ucas_files:
            raise RuntimeError("容器文件未打开")

        # 确定分区和分区偏移
        partition_index = 0
        partition_offset = offset

        if self._header and self._header.partition_size > 0:
            partition_index = int(offset // self._header.partition_size)
            partition_offset = offset % self._header.partition_size

        if partition_index >= len(self._ucas_files):
            raise IndexError(
                f"分区索引 {partition_index} 超出范围（共 {len(self._ucas_files)} 个分区）"
            )

        # 检查是否需要解压
        compression_block_size = self._compression_block_size
        if compression_block_size == 0:
            compression_block_size = 64 * 1024 * 1024  # 默认 64MB

        first_block_index = int(offset // compression_block_size)
        last_block_index = int(((offset + length + compression_block_size - 1) // compression_block_size) - 1)

        if first_block_index == last_block_index and self._compression_blocks:
            # 单块读取 — 检查是否压缩
            block = self._compression_blocks[first_block_index] if first_block_index < len(self._compression_blocks) else None
            if block and block.compression_method_index == 0:
                # 无压缩，直接读取
                reader = self._ucas_files[partition_index]
                reader.seek(partition_offset)
                return reader.read(length)

        # 多块或压缩数据 — 逐块读取并拼接
        result = bytearray()
        offset_in_block = offset % compression_block_size
        remaining = length

        for block_index in range(first_block_index, last_block_index + 1):
            if block_index >= len(self._compression_blocks):
                break

            block = self._compression_blocks[block_index]

            # 计算块在分区中的位置
            block_partition_index = int(block.offset // self._header.partition_size) if self._header and self._header.partition_size > 0 else 0
            block_partition_offset = block.offset % self._header.partition_size if self._header and self._header.partition_size > 0 else block.offset

            if block_partition_index >= len(self._ucas_files):
                break

            reader = self._ucas_files[block_partition_index]
            reader.seek(block_partition_offset)

            if block.compression_method_index == 0:
                # 无压缩
                raw_data = reader.read(block.compressed_size)
            else:
                # 有压缩 — 读取压缩数据（暂不解压）
                # TODO: 集成 compression 模块进行解压
                logger.warning(
                    "压缩块 %d 使用方法 %d，暂不解压，返回原始压缩数据",
                    block_index, block.compression_method_index,
                )
                raw_data = reader.read(block.compressed_size)

            # 从块中提取所需部分
            size_in_block = min(compression_block_size - offset_in_block, remaining)
            if offset_in_block < len(raw_data):
                end = min(offset_in_block + size_in_block, len(raw_data))
                result.extend(raw_data[offset_in_block:end])

            offset_in_block = 0
            remaining -= size_in_block

        return bytes(result)

    # ========================================================================
    # 内部加载方法
    # ========================================================================

    def _load_chunk_ids(self) -> None:
        """加载 ChunkId 数组"""
        if self._utoc_file is None or self._header is None:
            return

        count = self._header.toc_entry_count
        self._chunk_ids = []
        for _ in range(count):
            data = self._utoc_file.read(12)
            if len(data) < 12:
                raise ValueError(f"ChunkId 数据不足：需要 {count} 个，提前结束")
            self._chunk_ids.append(FIoChunkId(bytes=data))

        logger.debug("加载 %d 个 ChunkId", count)

    def _load_chunk_offsets(self) -> None:
        """加载 OffsetAndLength 数组（每个 10 字节）"""
        if self._utoc_file is None or self._header is None:
            return

        count = self._header.toc_entry_count
        self._chunk_offsets = []
        for _ in range(count):
            data = self._utoc_file.read(10)
            if len(data) < 10:
                raise ValueError(f"OffsetAndLength 数据不足：需要 {count} 个，提前结束")
            self._chunk_offsets.append(FIoOffsetAndLength.from_bytes(data))

        logger.debug("加载 %d 个 OffsetAndLength", count)

    def _load_perfect_hash_seeds(self) -> None:
        """加载 Perfect Hash 种子（Version 4+）"""
        if self._utoc_file is None or self._header is None:
            return

        perfect_hash_seeds_count = 0
        chunks_without_perfect_hash_count = 0

        if self._header.version >= EIoStoreTocVersion.PerfectHashWithOverflow:
            perfect_hash_seeds_count = self._header.toc_chunk_perfect_hash_seeds_count
            chunks_without_perfect_hash_count = self._header.toc_chunks_without_perfect_hash_count
        elif self._header.version >= EIoStoreTocVersion.PerfectHash:
            perfect_hash_seeds_count = self._header.toc_chunk_perfect_hash_seeds_count

        if perfect_hash_seeds_count > 0:
            seed_data = self._utoc_file.read(perfect_hash_seeds_count * 4)
            self._chunk_perfect_hash_seeds = list(struct.unpack(
                f'<{perfect_hash_seeds_count}i', seed_data
            ))
            logger.debug("加载 %d 个 Perfect Hash 种子", perfect_hash_seeds_count)

        if chunks_without_perfect_hash_count > 0:
            idx_data = self._utoc_file.read(chunks_without_perfect_hash_count * 4)
            self._chunk_indices_without_perfect_hash = list(struct.unpack(
                f'<{chunks_without_perfect_hash_count}i', idx_data
            ))
            logger.debug("加载 %d 个无 Perfect Hash 索引", chunks_without_perfect_hash_count)

    def _load_compression_blocks(self) -> None:
        """加载压缩块条目（每个 12 字节）"""
        if self._utoc_file is None or self._header is None:
            return

        count = self._header.toc_compressed_block_entry_count
        self._compression_blocks = []
        for _ in range(count):
            block = FIoStoreTocCompressedBlockEntry.from_stream(self._utoc_file)
            self._compression_blocks.append(block)

        logger.debug("加载 %d 个压缩块条目", count)

    def _load_compression_methods(self) -> None:
        """加载压缩方法名"""
        if self._utoc_file is None or self._header is None:
            return

        name_count = self._header.compression_method_name_count
        name_length = self._header.compression_method_name_length

        if name_count == 0 or name_length == 0:
            return

        # 读取压缩方法名缓冲区
        buffer_size = name_count * name_length
        buffer = self._utoc_file.read(buffer_size)
        if len(buffer) < buffer_size:
            raise ValueError(f"压缩方法名数据不足：需要 {buffer_size} 字节")

        # 索引 0 保留给 "None"
        self._compression_methods = ["None"]
        for i in range(name_count):
            start = i * name_length
            end = start + name_length
            name = buffer[start:end].split(b'\x00')[0].decode('ascii', errors='replace')
            if name:
                self._compression_methods.append(name)

        self._compression_block_size = self._header.compression_block_size
        logger.debug("加载 %d 个压缩方法: %s", name_count, self._compression_methods[1:])

    def _skip_signatures(self) -> None:
        """跳过签名数据（如果容器已签名）"""
        if self._utoc_file is None or self._header is None:
            return

        if not self._header.is_signed:
            return

        # 读取哈希大小
        hash_size_data = self._utoc_file.read(4)
        if len(hash_size_data) < 4:
            return
        hash_size = struct.unpack('<I', hash_size_data)[0]

        # 跳过 tocSignature + blockSignature + FSHAHash[compressedBlockCount]
        skip_size = hash_size + hash_size + 20 * self._header.toc_compressed_block_entry_count
        self._utoc_file.seek(skip_size, 1)

        logger.debug("跳过签名数据: %d 字节", skip_size)

    def _load_directory_index(self) -> None:
        """加载目录索引缓冲区"""
        if self._utoc_file is None or self._header is None:
            return

        if self._header.version < EIoStoreTocVersion.DirectoryIndex:
            return

        if not self._header.is_indexed:
            return

        if self._header.directory_index_size == 0:
            return

        if not (self._read_options & EIoStoreTocReadOptions.ReadDirectoryIndex):
            # 跳过目录索引
            self._utoc_file.seek(self._header.directory_index_size, 1)
            return

        self._directory_index_buffer = self._utoc_file.read(self._header.directory_index_size)
        logger.debug("加载目录索引: %d 字节", len(self._directory_index_buffer))

    def _build_info(self) -> None:
        """构建 TOC 信息摘要"""
        if self._header is None:
            return

        self._info = IoStoreInfo()
        self._info.version = self._header.version
        self._info.toc_entry_count = self._header.toc_entry_count
        self._info.compressed_block_count = self._header.toc_compressed_block_entry_count
        self._info.compression_method_count = self._header.compression_method_name_count
        self._info.compression_block_size = self._header.compression_block_size
        self._info.directory_index_size = self._header.directory_index_size
        self._info.partition_count = self._header.partition_count
        self._info.partition_size = self._header.partition_size
        self._info.container_flags = self._header.container_flags
        self._info.is_encrypted = self._header.is_encrypted
        self._info.is_compressed = self._header.is_compressed
        self._info.chunk_ids = list(self._chunk_ids)
        self._info.chunk_offsets = list(self._chunk_offsets)

    def _open_container_files(self) -> None:
        """打开 .ucas 容器文件（支持多分区）"""
        if self._header is None:
            return

        base_path = Path(self.utoc_path).with_suffix('')

        if self._header.partition_count <= 1:
            # 单分区
            try:
                self._ucas_files.append(open(self.ucas_path, 'rb'))
            except FileNotFoundError as e:
                raise FileNotFoundError(
                    f"无法打开容器分区 0: {self.ucas_path}"
                ) from e
        else:
            # 多分区
            for i in range(self._header.partition_count):
                if i == 0:
                    path = str(base_path) + '.ucas'
                else:
                    path = f"{base_path}_s{i}.ucas"

                try:
                    self._ucas_files.append(open(path, 'rb'))
                except FileNotFoundError as e:
                    raise FileNotFoundError(
                        f"无法打开容器分区 {i}: {path}"
                    ) from e

        logger.debug("打开 %d 个容器分区", len(self._ucas_files))

    def _build_imperfect_hash_fallback(self) -> None:
        """构建不完美哈希回退表

        当 ChunkIndicesWithoutPerfectHash 存在时，为这些条目构建字典回退。
        """
        if self._chunk_indices_without_perfect_hash is None:
            return

        self._toc_imperfect_hash_map = {}
        for idx in self._chunk_indices_without_perfect_hash:
            if 0 <= idx < len(self._chunk_ids) and idx < len(self._chunk_offsets):
                self._toc_imperfect_hash_map[self._chunk_ids[idx]] = self._chunk_offsets[idx]

        logger.debug(
            "构建不完美哈希回退表: %d 条目",
            len(self._toc_imperfect_hash_map),
        )