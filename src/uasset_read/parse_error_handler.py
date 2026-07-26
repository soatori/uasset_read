"""Parse error handler -- re-export shim.

All error handling logic now lives in ``uasset_read.pipeline.error_handler``.
This module re-exports ``_handle_parse_error`` so that existing import paths
continue to work unchanged (task #458).
"""
from uasset_read.pipeline.error_handler import _handle_parse_error  # noqa: F401
