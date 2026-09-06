"""Payload models for large binary data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PayloadDescriptor:
    """Descriptor for a large payload that can be extracted on demand."""

    kind: Literal["ubulk", "uexp", "uptnl", "other"]
    offset: int
    size: int
    compressed_size: int | None = None
    compression_flags: int = 0

    @property
    def is_compressed(self) -> bool:
        return self.compressed_size is not None and self.compressed_size > 0


@dataclass
class PayloadExtraction:
    """Result of payload extraction."""

    descriptor: PayloadDescriptor
    data: bytes
    extracted: bool = True
    error: str | None = None
