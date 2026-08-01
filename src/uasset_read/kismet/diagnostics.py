"""
Kismet Bytecode Diagnostics — bounded candidate scanning for diagnostic purposes.

Provides scan_function_export_for_diagnostics which scans export serial bytes
for parseable expression streams. Results are diagnostic-only dataclasses
and cannot be used as decompilation results.
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

from uasset_read.kismet.bytecode_extractor import (
    _PLAUSIBLE_SCRIPT_START_TOKENS,
    _MAX_SCAN_ATTEMPTS,
    _MAX_CANDIDATE_SIZE,
    _has_false_positive_pattern,
    parse_bytecode_stream,
)
from uasset_read.exceptions import ParseError

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BytecodeCandidateDiagnostic:
    """Diagnostic-only information about a bytecode candidate found during serial scanning.

    This dataclass contains only offset and count information plus any validation
    error. It is NOT a decompilation result and must never be used as one.
    """
    start_offset: int
    end_offset: int
    expression_count: int
    validation_error: str | None


def scan_function_export_for_diagnostics(
    archive: FArchive,
    export: ObjectExport,
    summary: PackageFileSummary,
    name_map: list[str],
    import_map: list,
    export_map: list,
) -> list[BytecodeCandidateDiagnostic]:
    """Scan export serial bytes for parseable bytecode candidates (diagnostic only).

    Returns a list of BytecodeCandidateDiagnostic with start/end offsets,
    expression counts, and any validation errors. These are diagnostic
    artifacts and must never be consumed as decompilation results.

    Args:
        archive: FArchive instance (file-level archive)
        export: ObjectExport to scan
        summary: PackageFileSummary for version info
        name_map: Name table for expression resolution
        import_map: Import table for class resolution
        export_map: Export table for class resolution

    Returns:
        List of BytecodeCandidateDiagnostic (may be empty).
    """
    original_pos = archive.tell()
    try:
        archive.seek(export.serial_offset)
        data = archive.read_bytes(export.serial_size)
    finally:
        archive.seek(original_pos)

    candidates: list[BytecodeCandidateDiagnostic] = []
    end_positions = [idx for idx, b in enumerate(data) if b == 0x53]
    attempts = 0

    for start, first in enumerate(data):
        if first not in _PLAUSIBLE_SCRIPT_START_TOKENS:
            continue
        for end in end_positions:
            if end < start:
                continue
            candidate = data[start:end + 1]
            if len(candidate) < 2:
                continue
            if len(candidate) > _MAX_CANDIDATE_SIZE:
                break
            if _has_false_positive_pattern(candidate):
                continue

            attempts += 1
            if attempts > _MAX_SCAN_ATTEMPTS:
                logger.debug(
                    "Diagnostic scan for '%s': hit _MAX_SCAN_ATTEMPTS (%d), stopping",
                    export.object_name, _MAX_SCAN_ATTEMPTS,
                )
                return candidates

            try:
                expressions = parse_bytecode_stream(candidate, name_map, tolerant=True)
                candidates.append(BytecodeCandidateDiagnostic(
                    start_offset=export.serial_offset + start,
                    end_offset=export.serial_offset + end + 1,
                    expression_count=len(expressions),
                    validation_error=None,
                ))
            except (struct.error, ValueError, IndexError, ParseError,
                    KeyError, TypeError, AttributeError, OverflowError) as exc:
                candidates.append(BytecodeCandidateDiagnostic(
                    start_offset=export.serial_offset + start,
                    end_offset=export.serial_offset + end + 1,
                    expression_count=0,
                    validation_error=str(exc),
                ))
            break

    return candidates
