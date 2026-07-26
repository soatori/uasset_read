"""Memory cleanup -- re-export shim.

All memory cleanup logic now lives in ``uasset_read.pipeline.memory``.  This
module re-exports ``_cleanup_parse_memory`` so that existing import paths
continue to work unchanged (task #458).
"""
from uasset_read.pipeline.memory import _cleanup_parse_memory  # noqa: F401
