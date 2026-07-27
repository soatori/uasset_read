from __future__ import annotations

"""IoStore Reader — UE5.3+ IoStore container reader

Equivalent implementation of IoStoreReader.cs
Supports TOC parsing, Chunk lookup, Perfect Hash optimization, compressed block reading
"""
from io import BytesIO
from typing import BinaryIO, Dict, List, Optional, Tuple
from pathlib import Path
import struct
import logging

from uasset_read.iostore.structures import (
    FIoChunkId,
    FIoOffsetAndLength,
    FIoStoreTocHeader,
    FIoStoreTocCompressedBlockEntry,
    FIoDirectoryIndexEntry,
    FIoFileIndexEntry,
    EIoStoreTocVersion,
    EIoStoreTocReadOptions,
)
from uasset_read.pak.decompress import decompress_block
from uasset_read.pak.crypto import decrypt_aes_ecb
from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)

# Resource limit constants — prevent malicious UTOC headers from exhausting resources
MAX_TOC_ENTRIES = 1_000_000          # Maximum Chunk entry count
MAX_COMPRESSION_BLOCKS = 1_000_000   # Maximum compression block count
MAX_COMPRESSION_METHODS = 100        # Maximum compression method count
MAX_METHOD_NAME_LENGTH = 256         # Maximum single method name length
MAX_DIRECTORY_INDEX_BYTES = 64 * 1024 * 1024  # Directory index maximum 64MB
MAX_PARTITION_COUNT = 64             # Maximum partition count
MAX_DIRECTORY_ARRAY_COUNT = 1_000_000  # Maximum directory/file index entry count
MAX_STRING_TABLE_COUNT = 1_000_000      # Maximum string table entry count


class IoStoreInfo:
    """Summary information after parsing IoStore TOC"""
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
    """IoStore container reader

    Equivalent implementation of IoStoreReader.cs, supports:
    - TOC header parsing (all versions 1-8)
    - ChunkId and OffsetAndLength loading
    - Perfect Hash optimized lookup (Version 4+)
    - Compressed block entry parsing
    - Compression method name loading
    - Directory index loading (optional)
    - Partition support (Version 3+)

    Usage:
        reader = IoStoreReader("game.utoc", "game.ucas")
        reader.open()
        data = reader.extract(chunk_id_bytes)
        reader.close()

    # Or use context manager
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
        """Initialize IoStoreReader

        Args:
            utoc_path: .utoc file path
            ucas_path: .ucas file path (optional, auto-derived from utoc path)
            aes_key: AES decryption key (optional)
            tolerant: Tolerant mode, do not throw exceptions on non-fatal errors
            read_options: TOC read options
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

        # Chunk lookup related
        self._chunk_ids: List[FIoChunkId] = []
        self._chunk_offsets: List[FIoOffsetAndLength] = []
        self._chunk_perfect_hash_seeds: Optional[List[int]] = None
        self._chunk_indices_without_perfect_hash: Optional[List[int]] = None
        self._toc_imperfect_hash_map: Optional[Dict[FIoChunkId, FIoOffsetAndLength]] = None

        # Compression related
        self._compression_blocks: List[FIoStoreTocCompressedBlockEntry] = []
        self._compression_methods: List[str] = ["None"]  # Index 0 = no compression
        self._compression_block_size: int = 0

        # Directory index
        self._directory_index_buffer: Optional[bytes] = None
        self._mount_point: str = ""
        self._directory_index: Dict[str, FIoChunkId] = {}

    @property
    def ucas_path(self) -> str:
        """Get .ucas file path"""
        if self._ucas_path_override:
            return self._ucas_path_override
        # Derive from utoc path
        p = Path(self.utoc_path)
        return str(p.with_suffix('.ucas'))

    @property
    def info(self) -> Optional[IoStoreInfo]:
        """Parsed TOC information"""
        return self._info

    @property
    def header(self) -> Optional[FIoStoreTocHeader]:
        """TOC header"""
        return self._header

    @property
    def mount_point(self) -> str:
        """Mount point"""
        return self._mount_point

    @property
    def is_encrypted(self) -> bool:
        """Whether container is encrypted"""
        return self._header.is_encrypted if self._header else False

    @property
    def is_compressed(self) -> bool:
        """Whether container is compressed"""
        return self._header.is_compressed if self._header else False

    @property
    def chunk_count(self) -> int:
        """Chunk count"""
        return len(self._chunk_ids)

    def open(self) -> None:
        """Open IoStore TOC and CAS files

        Read the complete TOC structure, including:
        - Header (144 bytes)
        - ChunkId array
        - OffsetAndLength array (10 bytes/entry)
        - Perfect Hash seeds (Version 4+)
        - Compressed block entries
        - Compression method names
        - Directory index (optional)
        """
        logger.debug("Opening IoStore: utoc=%s", self.utoc_path)

        self._utoc_file = open(self.utoc_path, 'rb')

        try:
            # Read and validate TOC header
            self._header = FIoStoreTocHeader.from_stream(self._utoc_file)

            # Align to 4-byte boundary (UE source: Ar.Position.Align(4))
            current_pos = self._utoc_file.tell()
            aligned_pos = (current_pos + 3) & ~3
            if aligned_pos != current_pos:
                self._utoc_file.seek(aligned_pos)

            # No partition support before Version 3
            if self._header.version < EIoStoreTocVersion.PartitionSize:
                self._header.partition_count = 1
                self._header.partition_size = 0xFFFFFFFFFFFFFFFF  # ulong.MaxValue

            # Load ChunkId array
            self._load_chunk_ids()

            # Load OffsetAndLength array
            self._load_chunk_offsets()

            # Load Perfect Hash seeds (Version 4+)
            self._load_perfect_hash_seeds()

            # Load compressed block entries
            self._load_compression_blocks()

            # Load compression method names
            self._load_compression_methods()

            # Skip signature data (if present)
            self._skip_signatures()

            # Load directory index (if present and requested)
            self._load_directory_index()

            # Build Info summary
            self._build_info()

            # Open container files (.ucas)
            self._open_container_files()

            # If using Perfect Hash, build imperfect hash fallback table
            if self._chunk_perfect_hash_seeds is not None:
                self._build_imperfect_hash_fallback()

            logger.debug(
                "IoStore opened: version=%d, chunks=%d, compression_blocks=%d, methods=%s",
                self._header.version,
                len(self._chunk_ids),
                len(self._compression_blocks),
                self._compression_methods,
            )

        except (OSError, struct.error, ValueError, ParseError):
            self.close()
            raise

    def close(self) -> None:
        """Close all file handles"""
        if self._utoc_file:
            try:
                self._utoc_file.close()
            except OSError as e:
                logger.debug("Failed to close utoc file: %s", e)
            self._utoc_file = None

        for f in self._ucas_files:
            try:
                f.close()
            except OSError as e:
                logger.debug("Failed to close ucas file: %s", e)
        self._ucas_files.clear()

    def __del__(self) -> None:
        """Safety net: ensure file handles are released."""
        try:
            self.close()
        except Exception:
            logger.debug("IoStoreReader.__del__ cleanup failed", exc_info=True)

    def __enter__(self) -> IoStoreReader:
        self.open()
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        self.close()

    def list_files(self) -> List[str]:
        """List all file paths (requires directory index)"""
        return list(self._directory_index.keys())

    def does_chunk_exist(self, chunk_id: FIoChunkId) -> bool:
        """Check if ChunkId exists"""
        offset_length = self._resolve_chunk(chunk_id)
        return offset_length is not None

    def try_resolve(self, chunk_id: FIoChunkId) -> Optional[Tuple[int, int]]:
        """Try to resolve ChunkId to (offset, length)

        Args:
            chunk_id: Chunk identifier

        Returns:
            (offset, length) tuple, returns None if not found
        """
        offset_length = self._resolve_chunk(chunk_id)
        if offset_length is not None:
            return (offset_length.offset, offset_length.length)
        return None

    def extract(self, chunk_id_bytes: bytes) -> bytes:
        """Extract data by ChunkId raw bytes

        Args:
            chunk_id_bytes: 12-byte ChunkId

        Returns:
            Extracted raw data (decompressed)

        Raises:
            ValueError: ChunkId is invalid or not found
            NotImplementedError: Decompression not yet implemented
        """
        if len(chunk_id_bytes) != 12:
            raise ValueError(f"ChunkId must be 12 bytes, actual {len(chunk_id_bytes)} bytes")

        chunk_id = FIoChunkId(bytes=chunk_id_bytes)
        return self.read_chunk(chunk_id)

    def extract_path(self, path: str) -> Optional[bytes]:
        """Extract a file by directory-index path."""
        normalized = path.replace("\\", "/").strip("/")
        candidates = [normalized]
        if "." not in normalized.rsplit("/", 1)[-1]:
            candidates.extend(
                f"{normalized}{suffix}" for suffix in (".uasset", ".uexp", ".ubulk", ".umap")
            )
        chunk_id = self._directory_index.get(path) or self._directory_index.get(normalized)
        if chunk_id is None:
            lowered_candidates = [candidate.lower() for candidate in candidates]
            for candidate, candidate_chunk in self._directory_index.items():
                lowered = candidate.lower().strip("/")
                if any(lowered == item or lowered.endswith(f"/{item}") for item in lowered_candidates):
                    return self.read_chunk(candidate_chunk)
        if chunk_id is None:
            return None
        return self.read_chunk(chunk_id)

    def read_chunk(self, chunk_id: FIoChunkId) -> bytes:
        """Read data by FIoChunkId

        Args:
            chunk_id: Chunk identifier

        Returns:
            Decompressed data

        Raises:
            KeyError: ChunkId not found
        """
        offset_length = self._resolve_chunk(chunk_id)
        if offset_length is None:
            raise KeyError(f"Chunk not found: {chunk_id.bytes.hex()}")

        return self._read_data(offset_length.offset, offset_length.length)

    def _resolve_chunk(self, chunk_id: FIoChunkId) -> Optional[FIoOffsetAndLength]:
        """Resolve ChunkId to OffsetAndLength

        Prefer Perfect Hash (O(1)), fall back to imperfect hash table or linear search.
        """
        if self._chunk_perfect_hash_seeds is not None:
            return self._resolve_chunk_perfect_hash(chunk_id)

        # Fallback: imperfect hash table or linear search
        return self._resolve_chunk_imperfect(chunk_id)

    def _resolve_chunk_perfect_hash(self, chunk_id: FIoChunkId) -> Optional[FIoOffsetAndLength]:
        """Resolve ChunkId using Perfect Hash"""
        chunk_count = self._header.toc_entry_count
        if chunk_count == 0:
            return None

        seed_count = len(self._chunk_perfect_hash_seeds)
        seed_index = self._hash_with_seed(chunk_id, 0) % seed_count
        seed = self._chunk_perfect_hash_seeds[seed_index]

        if seed == 0:
            return None

        if seed < 0:
            # Imperfect hash entry
            seed_as_index = (-seed) - 1
            if seed_as_index < chunk_count:
                slot = seed_as_index
            else:
                # Fall back to imperfect hash lookup
                return self._resolve_chunk_imperfect(chunk_id)
        else:
            slot = self._hash_with_seed(chunk_id, seed) % chunk_count

        if slot < len(self._chunk_ids) and self._chunk_ids[slot] == chunk_id:
            return self._chunk_offsets[slot]

        return None

    def _resolve_chunk_imperfect(self, chunk_id: FIoChunkId) -> Optional[FIoOffsetAndLength]:
        """Imperfect hash fallback lookup"""
        if self._toc_imperfect_hash_map is not None:
            return self._toc_imperfect_hash_map.get(chunk_id)

        # Linear search
        for i, cid in enumerate(self._chunk_ids):
            if cid == chunk_id:
                return self._chunk_offsets[i]
        return None

    def _hash_with_seed(self, chunk_id: FIoChunkId, seed: int) -> int:
        """HashWithSeed implementation

        Uses 64-bit FNV-1a hash algorithm (consistent with UE source)
        - Initial value: 0xcbf29ce484222325 (FNV offset basis)
        - Prime: 0x00000100000001B3 (FNV prime)
        """
        data = chunk_id.bytes
        hash_val = 0xcbf29ce484222325 ^ seed  # FNV offset basis (64-bit)
        for byte in data:
            hash_val ^= byte
            hash_val = (hash_val * 0x00000100000001B3) & 0xFFFFFFFFFFFFFFFF  # FNV prime, 64-bit
        return hash_val

    def _read_data(self, offset: int, length: int) -> bytes:
        """Read data from .ucas file

        Currently only supports uncompressed, unencrypted blocks. Fail explicitly
        when encountering encrypted/compressed data to avoid returning unparseable
        raw compressed or encrypted data.
        """
        if not self._ucas_files:
            raise RuntimeError("Container file not opened")
        if self._header and self._header.is_encrypted and self._aes_key is None:
            raise ValueError("IoStore encrypted chunk extraction requires AES key")

        # Determine partition and partition offset
        partition_index = 0
        partition_offset = offset

        if self._header and self._header.partition_size > 0:
            partition_index = int(offset // self._header.partition_size)
            partition_offset = offset % self._header.partition_size

        if partition_index >= len(self._ucas_files):
            raise IndexError(
                f"Partition index {partition_index} out of range (total {len(self._ucas_files)} partitions)"
            )

        # Check if decompression is needed
        compression_block_size = self._compression_block_size
        if compression_block_size == 0:
            compression_block_size = 64 * 1024 * 1024  # Default 64MB

        first_block_index = int(offset // compression_block_size)
        last_block_index = int(((offset + length + compression_block_size - 1) // compression_block_size) - 1)

        if not self._compression_blocks:
            return self._read_uncompressed_partitions(partition_index, partition_offset, length)

        if first_block_index == last_block_index and self._compression_blocks:
            # Single block read — check if compressed
            block = self._compression_blocks[first_block_index] if first_block_index < len(self._compression_blocks) else None
            if block and block.compression_method_index == 0:
                # No compression, read directly
                if self._header and self._header.is_encrypted:
                    physical_offset = block.offset + (offset % compression_block_size)
                    if self._header.partition_size > 0:
                        block_partition_index = int(physical_offset // self._header.partition_size)
                        block_partition_offset = physical_offset % self._header.partition_size
                    else:
                        block_partition_index = 0
                        block_partition_offset = physical_offset
                    if block_partition_index >= len(self._ucas_files):
                        raise ParseError(
                            f"IoStore partition index {block_partition_index} out of range "
                            f"(total {len(self._ucas_files)} partitions)"
                        )
                    return self._read_encrypted_range(
                        self._ucas_files[block_partition_index],
                        block_partition_offset,
                        length,
                        "IoStore uncompressed block read insufficient",
                    )
                reader = self._ucas_files[partition_index]
                reader.seek(partition_offset)
                raw = reader.read(length)
                if len(raw) < length:
                    raise ParseError(
                        f"IoStore uncompressed block read insufficient: {len(raw)} < {length} bytes"
                    )
                return raw

        # Multi-block or compressed data — read block by block and concatenate
        result = bytearray()
        offset_in_block = offset % compression_block_size
        remaining = length

        for block_index in range(first_block_index, last_block_index + 1):
            if block_index >= len(self._compression_blocks):
                raise ParseError(
                    f"IoStore compression block index {block_index} out of range (total {len(self._compression_blocks)} blocks)"
                )

            block = self._compression_blocks[block_index]

            # Calculate block position in partition
            block_partition_index = int(block.offset // self._header.partition_size) if self._header and self._header.partition_size > 0 else 0
            block_partition_offset = block.offset % self._header.partition_size if self._header and self._header.partition_size > 0 else block.offset

            if block_partition_index >= len(self._ucas_files):
                raise ParseError(
                    f"IoStore partition index {block_partition_index} out of range (total {len(self._ucas_files)} partitions)"
                )

            reader = self._ucas_files[block_partition_index]
            reader.seek(block_partition_offset)

            raw_data = reader.read(block.compressed_size)
            if len(raw_data) < block.compressed_size:
                raise ParseError(
                    f"IoStore compressed block {block_index} read insufficient: {len(raw_data)} < {block.compressed_size} bytes"
                )
            if self._header and self._header.is_encrypted:
                aligned_size = (block.compressed_size + 15) & ~15
                if len(raw_data) < aligned_size:
                    extra = reader.read(aligned_size - len(raw_data))
                    raw_data += extra
                    if len(raw_data) < aligned_size:
                        raise ParseError(
                            f"IoStore encrypted block {block_index} aligned read insufficient: "
                            f"{len(raw_data)} < {aligned_size} bytes"
                        )
                raw_data = decrypt_aes_ecb(raw_data, self._aes_key)[:block.compressed_size]

            method = self._compression_method_name(block.compression_method_index)
            raw_data = decompress_block(raw_data, block.uncompressed_size, method)

            # Extract required portion from block
            size_in_block = min(compression_block_size - offset_in_block, remaining)
            if offset_in_block < len(raw_data):
                end = min(offset_in_block + size_in_block, len(raw_data))
                result.extend(raw_data[offset_in_block:end])

            offset_in_block = 0
            remaining -= size_in_block

        return bytes(result)

    def _read_encrypted_range(
        self,
        reader: BinaryIO,
        offset: int,
        length: int,
        error_prefix: str,
    ) -> bytes:
        """Read and decrypt an AES-ECB range without decrypting partial blocks."""
        if length == 0:
            return b""

        aligned_offset = offset & ~15
        aligned_end = (offset + length + 15) & ~15
        aligned_length = aligned_end - aligned_offset

        reader.seek(aligned_offset)
        ciphertext = reader.read(aligned_length)
        if len(ciphertext) < aligned_length:
            raise ParseError(
                f"{error_prefix}: {len(ciphertext)} < {aligned_length} bytes"
            )

        plaintext = decrypt_aes_ecb(ciphertext, self._aes_key)
        slice_offset = offset - aligned_offset
        return plaintext[slice_offset:slice_offset + length]

    def _read_uncompressed_partitions(self, partition_index: int, partition_offset: int, length: int) -> bytes:
        """Read an uncompressed range, crossing UCAS partitions when necessary."""
        result = bytearray()
        remaining = length
        current_partition = partition_index
        current_offset = partition_offset
        while remaining > 0:
            if current_partition >= len(self._ucas_files):
                raise IndexError(
                    f"Partition index {current_partition} out of range (total {len(self._ucas_files)} partitions)"
                )
            reader = self._ucas_files[current_partition]
            reader.seek(current_offset)
            if self._header and self._header.partition_size > 0:
                readable = min(remaining, self._header.partition_size - current_offset)
            else:
                readable = remaining
            if self._header and self._header.is_encrypted:
                raw = self._read_encrypted_range(
                    reader,
                    current_offset,
                    readable,
                    "IoStore partition read insufficient",
                )
            else:
                reader.seek(current_offset)
                raw = reader.read(readable)
            if len(raw) < readable:
                raise ParseError(
                    f"IoStore partition read insufficient: read {len(raw)} < expected {readable} bytes "
                    f"(partition {current_partition})"
                )
            result.extend(raw)
            remaining -= readable
            current_partition += 1
            current_offset = 0
        return bytes(result)

    # ========================================================================
    # Internal loading methods
    # ========================================================================

    def _load_chunk_ids(self) -> None:
        """Load ChunkId array"""
        if self._utoc_file is None or self._header is None:
            return

        count = self._header.toc_entry_count
        if count > MAX_TOC_ENTRIES:
            raise ParseError(
                f"IoStore toc_entry_count {count} exceeds limit {MAX_TOC_ENTRIES}"
            )
        self._chunk_ids = []
        for _ in range(count):
            data = self._utoc_file.read(12)
            if len(data) < 12:
                raise ValueError(f"ChunkId data insufficient: need {count}, ended early")
            self._chunk_ids.append(FIoChunkId(bytes=data))

        logger.debug("Loaded %d ChunkIds", count)

    def _load_chunk_offsets(self) -> None:
        """Load OffsetAndLength array (10 bytes each)"""
        if self._utoc_file is None or self._header is None:
            return

        count = self._header.toc_entry_count
        self._chunk_offsets = []
        for _ in range(count):
            data = self._utoc_file.read(10)
            if len(data) < 10:
                raise ValueError(f"OffsetAndLength data insufficient: need {count}, ended early")
            self._chunk_offsets.append(FIoOffsetAndLength.from_bytes(data))

        logger.debug("Loaded %d OffsetAndLengths", count)

    def _load_perfect_hash_seeds(self) -> None:
        """Load Perfect Hash seeds (Version 4+)"""
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
            logger.debug("Loaded %d Perfect Hash seeds", perfect_hash_seeds_count)

        if chunks_without_perfect_hash_count > 0:
            idx_data = self._utoc_file.read(chunks_without_perfect_hash_count * 4)
            self._chunk_indices_without_perfect_hash = list(struct.unpack(
                f'<{chunks_without_perfect_hash_count}i', idx_data
            ))
            logger.debug("Loaded %d indices without Perfect Hash", chunks_without_perfect_hash_count)

    def _load_compression_blocks(self) -> None:
        """Load compression block entries (12 bytes each)"""
        if self._utoc_file is None or self._header is None:
            return

        count = self._header.toc_compressed_block_entry_count
        if count > MAX_COMPRESSION_BLOCKS:
            raise ParseError(
                f"IoStore compression block count {count} exceeds limit {MAX_COMPRESSION_BLOCKS}"
            )
        self._compression_blocks = []
        for _ in range(count):
            block = FIoStoreTocCompressedBlockEntry.from_stream(self._utoc_file)
            self._compression_blocks.append(block)

        logger.debug("Loaded %d compression block entries", count)

    def _load_compression_methods(self) -> None:
        """Load compression method names"""
        if self._utoc_file is None or self._header is None:
            return

        name_count = self._header.compression_method_name_count
        name_length = self._header.compression_method_name_length

        if name_count == 0 or name_length == 0:
            return

        if name_count > MAX_COMPRESSION_METHODS:
            raise ParseError(
                f"IoStore compression method count {name_count} exceeds limit {MAX_COMPRESSION_METHODS}"
            )
        if name_length > MAX_METHOD_NAME_LENGTH:
            raise ParseError(
                f"IoStore compression method name length {name_length} exceeds limit {MAX_METHOD_NAME_LENGTH}"
            )

        # Read compression method name buffer
        buffer_size = name_count * name_length
        buffer = self._utoc_file.read(buffer_size)
        if len(buffer) < buffer_size:
            raise ValueError(f"Compression method name data insufficient: need {buffer_size} bytes")

        # Index 0 is reserved for "None"
        self._compression_methods = ["None"]
        for i in range(name_count):
            start = i * name_length
            end = start + name_length
            name = buffer[start:end].split(b'\x00')[0].decode('ascii', errors='replace')
            if name:
                self._compression_methods.append(name)

        self._compression_block_size = self._header.compression_block_size
        logger.debug("Loaded %d compression methods: %s", name_count, self._compression_methods[1:])

    def _skip_signatures(self) -> None:
        """Skip signature data (if container is signed)"""
        if self._utoc_file is None or self._header is None:
            return

        if not self._header.is_signed:
            return

        # Read hash size
        hash_size_data = self._utoc_file.read(4)
        if len(hash_size_data) < 4:
            return
        hash_size = struct.unpack('<I', hash_size_data)[0]

        # Skip tocSignature + blockSignature + FSHAHash[compressedBlockCount]
        skip_size = hash_size + hash_size + 20 * self._header.toc_compressed_block_entry_count
        self._utoc_file.seek(skip_size, 1)

        logger.debug("Skipped signature data: %d bytes", skip_size)

    def _load_directory_index(self) -> None:
        """Load directory index buffer"""
        if self._utoc_file is None or self._header is None:
            return

        if self._header.version < EIoStoreTocVersion.DirectoryIndex:
            return

        if not self._header.is_indexed:
            return

        if self._header.directory_index_size == 0:
            return

        if self._header.directory_index_size > MAX_DIRECTORY_INDEX_BYTES:
            raise ParseError(
                f"IoStore directory index size {self._header.directory_index_size} exceeds limit {MAX_DIRECTORY_INDEX_BYTES}"
            )

        if not (self._read_options & EIoStoreTocReadOptions.ReadDirectoryIndex):
            # Skip directory index
            self._utoc_file.seek(self._header.directory_index_size, 1)
            return

        self._directory_index_buffer = self._utoc_file.read(self._header.directory_index_size)
        logger.debug("Loaded directory index: %d bytes", len(self._directory_index_buffer))
        self._parse_directory_index()

    def _parse_directory_index(self) -> None:
        """Parse UE IoStore directory index into path -> chunk id mapping."""
        if not self._directory_index_buffer:
            return

        data = self._directory_index_buffer
        if self._header and self._header.is_encrypted:
            if self._aes_key is None:
                raise ValueError("IoStore encrypted directory index requires AES key")
            data = decrypt_aes_ecb(data, self._aes_key)[:len(data)]

        stream = BytesIO(data)
        self._mount_point = self._normalize_mount_point(self._read_fstring_from(stream))
        directory_entries = self._read_array_from(stream, FIoDirectoryIndexEntry.deserialize)
        file_entries = self._read_array_from(stream, FIoFileIndexEntry.deserialize)
        string_table = self._read_string_table_from(stream)

        invalid = 0xFFFFFFFF
        self._directory_index.clear()

        def name_at(index: int) -> str:
            if index == invalid or index >= len(string_table):
                return ""
            return string_table[index]

        def join_path(base: str, name: str, is_file: bool = False) -> str:
            base = base.replace("\\", "/")
            if name:
                if base and not base.endswith("/"):
                    base += "/"
                base += name
            if is_file:
                return base
            return base.rstrip("/")

        MAX_DEPTH = 64
        MAX_ENTRIES = 100_000

        def read_index(dir_index: int, current_path: str, depth: int = 0,
                       visited_dirs: set | None = None,
                       visited_files: set | None = None) -> None:
            if visited_dirs is None:
                visited_dirs = set()
            if visited_files is None:
                visited_files = set()

            while dir_index != invalid and dir_index < len(directory_entries):
                if dir_index in visited_dirs:
                    raise ParseError(
                        f"IoStore directory index cycle: entry {dir_index} visited repeatedly"
                    )
                if depth > MAX_DEPTH:
                    raise ParseError(
                        f"IoStore directory index depth exceeds limit {MAX_DEPTH}"
                    )
                if len(visited_dirs) > MAX_ENTRIES:
                    raise ParseError(
                        f"IoStore directory index entry count exceeds limit {MAX_ENTRIES}"
                    )
                visited_dirs.add(dir_index)

                entry = directory_entries[dir_index]
                dir_name = name_at(entry.name)
                dir_path = join_path(current_path, dir_name)

                file_index = entry.first_file_entry
                while file_index != invalid and file_index < len(file_entries):
                    if file_index in visited_files:
                        raise ParseError(
                            f"IoStore file chain cycle: entry {file_index} visited repeatedly"
                        )
                    visited_files.add(file_index)

                    file_entry = file_entries[file_index]
                    full_path = join_path(dir_path, name_at(file_entry.name), is_file=True)
                    if file_entry.user_data < len(self._chunk_ids):
                        self._directory_index[full_path] = self._chunk_ids[file_entry.user_data]
                    file_index = file_entry.next_file_entry

                read_index(entry.first_child_entry, dir_path, depth + 1,
                           visited_dirs, visited_files)
                dir_index = entry.next_sibling_entry

        read_index(0, self._mount_point)
        logger.debug("Parsed directory index: %d files", len(self._directory_index))

    def _compression_method_name(self, index: int) -> str:
        if index == 0:
            return "None"
        if 0 <= index < len(self._compression_methods):
            return self._compression_methods[index]
        raise ValueError(f"IoStore compression method index out of range: {index}")

    @staticmethod
    def _normalize_mount_point(mount_point: str) -> str:
        mount = mount_point.replace("\\", "/")
        while mount.startswith("../"):
            mount = mount[3:]
        return mount.strip("/")

    @staticmethod
    def _read_array_from(stream: BytesIO, item_reader):
        count_data = stream.read(4)
        if len(count_data) < 4:
            raise ValueError("IoStore directory array count is truncated")
        count = struct.unpack("<i", count_data)[0]
        if count < 0:
            raise ValueError(f"IoStore directory array count is invalid: {count}")
        if count > MAX_DIRECTORY_ARRAY_COUNT:
            raise ParseError(
                f"IoStore directory array count {count} exceeds limit {MAX_DIRECTORY_ARRAY_COUNT}"
            )
        return [item_reader(stream) for _ in range(count)]

    @staticmethod
    def _read_string_table_from(stream: BytesIO) -> List[str]:
        count_data = stream.read(4)
        if len(count_data) < 4:
            raise ValueError("IoStore string table count is truncated")
        count = struct.unpack("<i", count_data)[0]
        if count < 0:
            raise ValueError(f"IoStore string table count is invalid: {count}")
        if count > MAX_STRING_TABLE_COUNT:
            raise ParseError(
                f"IoStore string table count {count} exceeds limit {MAX_STRING_TABLE_COUNT}"
            )
        return [IoStoreReader._read_fstring_from(stream) for _ in range(count)]

    @staticmethod
    def _read_fstring_from(stream: BytesIO) -> str:
        length_data = stream.read(4)
        if len(length_data) < 4:
            raise ValueError("FString length is truncated")
        length = struct.unpack("<i", length_data)[0]
        if length == 0:
            return ""
        if length < 0:
            byte_len = (-length) * 2
            raw = stream.read(byte_len)
            return raw[:-2].decode("utf-16-le", errors="replace")
        raw = stream.read(length)
        return raw[:-1].decode("utf-8", errors="replace")

    def _build_info(self) -> None:
        """Build TOC information summary"""
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
        """Open .ucas container files (supports multiple partitions)"""
        if self._header is None:
            return

        base_path = Path(self.utoc_path).with_suffix('')

        if self._header.partition_count <= 1:
            # Single partition
            try:
                self._ucas_files.append(open(self.ucas_path, 'rb'))
            except FileNotFoundError as e:
                raise FileNotFoundError(
                    f"Cannot open container partition 0: {self.ucas_path}"
                ) from e
        else:
            # Multiple partitions
            if self._header.partition_count > MAX_PARTITION_COUNT:
                raise ParseError(
                    f"IoStore partition count {self._header.partition_count} exceeds limit {MAX_PARTITION_COUNT}"
                )
            for i in range(self._header.partition_count):
                if i == 0:
                    path = str(base_path) + '.ucas'
                else:
                    path = f"{base_path}_s{i}.ucas"

                try:
                    self._ucas_files.append(open(path, 'rb'))
                except FileNotFoundError as e:
                    raise FileNotFoundError(
                        f"Cannot open container partition {i}: {path}"
                    ) from e

        logger.debug("Opened %d container partitions", len(self._ucas_files))

    def _build_imperfect_hash_fallback(self) -> None:
        """Build imperfect hash fallback table

        When ChunkIndicesWithoutPerfectHash exists, build dictionary fallback for these entries.
        """
        if self._chunk_indices_without_perfect_hash is None:
            return

        self._toc_imperfect_hash_map = {}
        for idx in self._chunk_indices_without_perfect_hash:
            if 0 <= idx < len(self._chunk_ids) and idx < len(self._chunk_offsets):
                self._toc_imperfect_hash_map[self._chunk_ids[idx]] = self._chunk_offsets[idx]

        logger.debug(
            "Built imperfect hash fallback table: %d entries",
            len(self._toc_imperfect_hash_map),
        )
