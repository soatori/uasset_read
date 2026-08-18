"""Oodle compression detection and decompression interface.

Detects Oodle-compressed data blocks and provides an interface for
decompression. Actual decompression requires the Oodle SDK or a
compatible decompression library.

Oodle compression is used in UE5 for:
- Compressed asset chunks (FCompressedChunkInfo)
- Bulk data compression
- IoStore container compression
- Pak file compression

Reference: Oodle Data Compression SDK by RAD Game Tools.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class OodleAlgorithm(Enum):
    """Oodle compression algorithms."""

    NONE = 0
    KRAKEN = 1
    LEVIATHAN = 2
    MERMAID = 3
    SELKIE = 4
    HYDRA = 5
    UNKNOWN = 0xFF


# Algorithm name mapping
_ALGORITHM_NAMES: dict[int, str] = {
    0: "None",
    1: "Kraken",
    2: "Leviathan",
    3: "Mermaid",
    4: "Selkie",
    5: "Hydra",
    0xFF: "Unknown",
}


@dataclass
class OodleBlockInfo:
    """Information about an Oodle-compressed block."""

    compressed_size: int
    decompressed_size: int
    algorithm: OodleAlgorithm
    data_offset: int = 0
    """Offset to compressed data in the file."""

    @property
    def compression_ratio(self) -> float:
        """Compression ratio (decompressed/compressed)."""
        if self.compressed_size == 0:
            return 0.0
        return self.decompressed_size / self.compressed_size

    @property
    def algorithm_name(self) -> str:
        return _ALGORITHM_NAMES.get(self.algorithm.value, "Unknown")


class OodleDetector:
    """Detect Oodle compression in asset data."""

    # Common Oodle signatures
    KRAKEN_MAGIC = 0x00010C0C  # Kraken compression header

    @staticmethod
    def detect_algorithm(data: bytes) -> OodleAlgorithm:
        """Detect Oodle algorithm from compressed data header.

        Args:
            data: Compressed data bytes

        Returns:
            Detected algorithm (or UNKNOWN if not recognized)
        """
        if len(data) < 4:
            return OodleAlgorithm.UNKNOWN

        # Check for common Oodle signatures
        # Note: Actual detection requires Oodle SDK headers
        # This is a heuristic detection based on known patterns
        first_byte = data[0]

        # Kraken uses specific bit patterns
        if first_byte & 0x0F in (0x0C, 0x0D):
            return OodleAlgorithm.KRAKEN
        elif first_byte & 0x0F in (0x0E, 0x0F):
            return OodleAlgorithm.LEVIATHAN
        elif first_byte & 0x0F in (0x08, 0x09):
            return OodleAlgorithm.MERMAID
        elif first_byte & 0x0F in (0x0A, 0x0B):
            return OodleAlgorithm.SELKIE

        return OodleAlgorithm.UNKNOWN

    @staticmethod
    def is_likely_oodle(data: bytes) -> bool:
        """Quick check if data is likely Oodle-compressed.

        Args:
            data: Compressed data bytes

        Returns:
            True if data appears to be Oodle-compressed
        """
        if len(data) < 4:
            return False

        algorithm = OodleDetector.detect_algorithm(data)
        return algorithm != OodleAlgorithm.UNKNOWN


def decompress_oodle(
    compressed_data: bytes,
    decompressed_size: int,
    algorithm: OodleAlgorithm = OodleAlgorithm.KRAKEN,
) -> Optional[bytes]:
    """Decompress Oodle-compressed data.

    Args:
        compressed_data: Compressed data bytes
        decompressed_size: Expected decompressed size
        algorithm: Compression algorithm to use

    Returns:
        Decompressed data, or None if decompression not available

    Note:
        This function requires an external Oodle decompression library.
        Currently returns None (decompression not available in zero-dependency build).
    """
    # Check if Oodle library is available
    try:
        import oodle_decompress  # type: ignore
        return oodle_decompress.decompress(
            compressed_data, decompressed_size, algorithm.value
        )
    except ImportError:
        pass

    # No Oodle library available
    return None


def format_oodle_info(block_info: OodleBlockInfo) -> str:
    """Format Oodle block information as readable text.

    Args:
        block_info: OodleBlockInfo to format

    Returns:
        Formatted text description
    """
    lines = [
        f"Oodle Block: {block_info.algorithm_name}",
        f"  Compressed size:   {block_info.compressed_size:,} bytes",
        f"  Decompressed size: {block_info.decompressed_size:,} bytes",
        f"  Compression ratio: {block_info.compression_ratio:.2f}x",
    ]
    return "\n".join(lines)
