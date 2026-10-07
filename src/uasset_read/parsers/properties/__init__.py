"""Bounded property reader package context type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PropertyPackageContext:
    """Package tables already decoded by the package reader."""

    summary: Any
    name_map: list[str]
    export_map: list[Any]
    import_map: list[Any]
