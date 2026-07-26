"""Unified parse error handling.

Extracted from ``uasset_read.parse_error_handler`` as part of the pipeline
consolidation (task #458).
"""
from __future__ import annotations

import logging

from uasset_read.exceptions import ParseError, VersionError
from uasset_read.memory_safety import MemoryLimitExceeded
from uasset_read.pipeline.stages import _record_parse_stage_error

logger = logging.getLogger(__name__)


def _handle_parse_error(
    exc: Exception,
    result,
    archive,
    path: str,
    tolerant: bool,
) -> None:
    """Unified handling of parse exceptions (VersionError / ParseError / MemoryError / Other).

    Note: Error recording is done uniformly via _record_parse_stage_error (with deduplication),
    and result.errors.append is no longer called separately to avoid duplicate recording.
    """

    if isinstance(exc, MemoryLimitExceeded):
        raise

    if isinstance(exc, VersionError):
        _record_parse_stage_error(result, archive, path, "version", "legacy_file_version", exc)
        result.is_success = False
    elif isinstance(exc, ParseError):
        _record_parse_stage_error(result, archive, path, "parse", "parse_error", exc)
        if exc.partial_result:
            for key, value in exc.partial_result.items():
                if hasattr(result, key):
                    setattr(result, key, value)
        result.is_success = False
    elif isinstance(exc, MemoryError):
        error_msg = f"MemoryError: {exc}"
        if error_msg not in result.errors:
            result.errors.append(error_msg)
        result.is_success = False
    else:
        _record_parse_stage_error(result, archive, path, "parse", "unexpected", exc)
        result.is_success = False

    if not tolerant:
        raise
