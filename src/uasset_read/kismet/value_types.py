"""Shared value types for native UFunction field parsing.

Provides the lossless ``FNameRef`` model used by native field declarations
and later by the dual-cursor Kismet archive.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FNameRef:
    """Lossless FName reference: raw index + number + resolved base name.

    Index zero is a legitimate null where UE permits it; nonzero invalid
    indices produce a structured failure rather than a guessed name.
    """

    name_index: int
    number: int
    base_name: str | None  # None when index is null or out-of-range
