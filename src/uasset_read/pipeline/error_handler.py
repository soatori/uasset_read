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
    """统一处理解析异常（VersionError / ParseError / MemoryError / 其他）。

    注意：错误记录统一通过 _record_parse_stage_error 完成（含去重），
    不再额外调用 result.errors.append，避免重复记录。
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
