"""VersionContext — immutable parse context.

Only carries what handlers read (``depth``). Version/layout facts live on
the package summary, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class VersionContext:
    """Immutable parse context. All readers share this."""

    depth: Literal["package", "object", "asset", "decode"] = "package"
