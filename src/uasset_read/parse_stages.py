"""Parse stage functions -- re-export shim.

All stage logic now lives in ``uasset_read.pipeline.stages``.  This module
re-exports every public name so that existing ``from uasset_read.parse_stages
import ...`` statements continue to work unchanged (task #458).
"""
from uasset_read.pipeline.stages import (  # noqa: F401
    _package_metadata,
    _record_parse_stage_error,
    _run_required_stage,
    _derive_package_name,
    _init_parse_env,
    _read_core_tables,
    _read_secondary_tables,
    _parse_export_properties,
    _create_linker,
    _read_package_headers,
)
