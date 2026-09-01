"""VersionContext — immutable parse context.

All v2 readers share this; handlers only consult the requested depth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class VersionContext:
    """Immutable parse context. All readers share this."""

    depth: Literal["package", "object", "asset", "decode"] = "package"
