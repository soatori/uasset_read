"""Post-processing stage -- re-export shim.

All post-processing logic now lives in ``uasset_read.pipeline.post_process``.
This module re-exports ``_post_process`` and ``_extract_kismet_decompiled`` so
that existing import paths continue to work unchanged (task #458).
"""
from uasset_read.pipeline.post_process import (  # noqa: F401
    _post_process,
    _extract_kismet_decompiled,
)
