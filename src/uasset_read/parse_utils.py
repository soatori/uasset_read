"""Parse utility functions -- re-export shim.

All parse utility logic now lives in ``uasset_read.pipeline.config``.  This
module re-exports every public name so that existing ``from uasset_read.parse_utils
import ...`` statements continue to work unchanged (task #458).
"""
from uasset_read.pipeline.config import (  # noqa: F401
    _should_use_lightweight_tolerant_parse,
    _is_large_file_asset,
    _build_lightweight_graphs,
    _build_lightweight_function_graphs,
    _apply_lightweight_parse,
    _resolve_parse_params,
)
