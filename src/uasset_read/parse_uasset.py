"""Core parse entry points -- re-export shim.

All core parse logic now lives in ``uasset_read.pipeline.core``.
This module re-exports every public name so that existing
``from uasset_read.parse_uasset import ...`` statements continue
to work unchanged (task #458).
"""
from __future__ import annotations

from uasset_read.pipeline.core import (  # noqa: F401
    _run_linker_post_load,
    _cleanup_archive_diagnostics,
    _parse_package_core,
    parse_package,
    parse_uasset,
    parse_uasset_with_linker,
    parse_package_lazy,
)
