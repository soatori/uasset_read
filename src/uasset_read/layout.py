"""Package layout detection — validated legacy vs zen vs unknown.

``PackageLayoutDetector.detect`` inspects a ``ByteSource`` and returns a
``PackageLayout`` describing which reader the bytes justify. Detection never
guesses from UE major version or file name (controller ruling: Zen has no
``PACKAGE_FILE_TAG``-style magic; container/package-store context is used when
available, otherwise structural/offset sanity of ``FZenPackageSummary`` — no
invented Zen magic constant). Unknown and container-only inputs are structured
``unknown`` results, never a Legacy parse of container metadata.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Literal

from uasset_read.constants import (
    MAX_EXPORT_COUNT,
    MAX_IMPORT_COUNT,
    MAX_NAME_COUNT,
    PACKAGE_FILE_TAG,
    PACKAGE_FILE_TAG_SWAPPED,
)
from uasset_read.sources import ByteSource

# FZenPackageSummary field offsets within the struct (AsyncLoading2.h:302-316):
# uint32 bHasVersioningInfo, uint32 HeaderSize, FMappedName Name (uint32),
# uint32 PackageFlags, uint32 _Unused, then int32 offset fields.
_ZEN_HEADER_SIZE = 4
# First offset field (ImportedPublicExportHashesOffset) starts at byte 20.
_ZEN_FIRST_OFFSET = 20
# ImportedPublicExportHashesOffset .. ImportedPackageNamesOffset (7 int32s).
_ZEN_OFFSET_COUNT = 7
_ZEN_SUMMARY_MIN_SIZE = _ZEN_FIRST_OFFSET + 4 * _ZEN_OFFSET_COUNT


@dataclass(frozen=True)
class PackageLayout:
    kind: Literal["legacy", "zen", "unknown"]
    detection_reason: str  # "validated_legacy" | "validated_zen" | "unknown"


def _validated_legacy(source: ByteSource) -> bool:
    """Structural validation of a PACKAGE_FILE_TAG-prefixed candidate.

    Bounded reads of TotalHeaderSize-adjacent header fields and the name /
    import / export counts; absurd counts (against remaining source size or
    catalog maxima) reject the candidate instead of trusting the tag alone.
    """
    size = source.size()
    if size is not None and size < 64:  # MIN_UASSET_SIZE
        return False
    try:
        head = source.read_at(0, 4)
    except Exception:
        return False
    if len(head) < 4:
        return False
    tag = struct.unpack_from("<I", head, 0)[0]
    if tag not in (PACKAGE_FILE_TAG, PACKAGE_FILE_TAG_SWAPPED):
        return False
    if tag == PACKAGE_FILE_TAG_SWAPPED:
        # Byte-order swapped packages are rejected by the Legacy reader
        # (VersionError); they are not a validated legacy candidate.
        return False

    # Validate through the existing summary reader: TotalHeaderSize, custom
    # versions, and the name/import/export counts must parse with sane
    # bounds. read_package_summary validate_offset()s the map offsets
    # (ExportOffset, CellExportOffset, ...) against the archive size without
    # seeking to them, so a fixed 64 KiB window alone would reject any real
    # package whose header maps sit beyond the window. Start with the cheap
    # bounded probe and escalate once to the full source before declaring
    # the candidate unknown. Absurd counts still reject the candidate.
    from uasset_read.archive import ByteArchive
    from uasset_read.serializers.package_summary import read_package_summary

    caps = [65536]
    if size is not None and size > 65536:
        caps.append(size)
    summary = None
    for cap in caps:
        read_len = cap if size is None else min(size, cap)
        try:
            data = source.read_at(0, read_len)
            summary, _total_decompressed = read_package_summary(ByteArchive(data))
        except Exception:
            # ParseError (offset beyond this window / absurd counts) or any
            # other summary failure: try the next larger window, else unknown.
            summary = None
            continue
        break
    if summary is None:
        return False
    if summary.total_header_size <= 0:
        return False
    if summary.name_count <= 0 or summary.name_count > MAX_NAME_COUNT:
        return False
    if summary.import_count < 0 or summary.import_count > MAX_IMPORT_COUNT:
        return False
    if summary.export_count < 0 or summary.export_count > MAX_EXPORT_COUNT:
        return False
    if size is not None and summary.total_header_size > size:
        return False
    return True


def _validated_zen(source: ByteSource) -> bool:
    """Structural/offset sanity of an ``FZenPackageSummary`` prefix.

    No magic constant: HeaderSize must fit the source, and the map offset
    fields must be monotonic and inside HeaderSize (controller ruling 1).
    """
    size = source.size()
    if size is None or size < _ZEN_SUMMARY_MIN_SIZE:
        return False
    try:
        blob = source.read_at(0, _ZEN_SUMMARY_MIN_SIZE)
    except Exception:
        return False
    if len(blob) < _ZEN_SUMMARY_MIN_SIZE:
        return False

    header_size = struct.unpack_from("<I", blob, _ZEN_HEADER_SIZE)[0]
    if header_size < _ZEN_SUMMARY_MIN_SIZE or header_size > size:
        return False

    offsets = list(struct.unpack_from(f"<{_ZEN_OFFSET_COUNT}i", blob, _ZEN_FIRST_OFFSET))
    # Offset fields are int32; negatives (absent optional tables such as
    # editor-only ImportedPackageNames) are allowed but must not be wild.
    # Require non-decreasing non-negative prefixes where present and every
    # non-negative offset inside HeaderSize.
    previous = 0
    for value in offsets:
        if value < -1:
            return False
        if value < 0:
            continue
        if value > header_size:
            return False
        if value < previous:
            return False
        previous = value
    return True


class PackageLayoutDetector:
    """Validate which reader the source bytes justify."""

    def detect(self, source: ByteSource) -> PackageLayout:
        try:
            head = source.read_at(0, 4)
        except Exception:
            return PackageLayout(kind="unknown", detection_reason="unknown")
        if len(head) < 4:
            return PackageLayout(kind="unknown", detection_reason="unknown")

        tag = struct.unpack_from("<I", head, 0)[0]
        if tag in (PACKAGE_FILE_TAG, PACKAGE_FILE_TAG_SWAPPED):
            if _validated_legacy(source):
                return PackageLayout(kind="legacy", detection_reason="validated_legacy")
            # Swapped tag or failed validation: not a readable legacy package.
            return PackageLayout(kind="unknown", detection_reason="unknown")

        if _validated_zen(source):
            return PackageLayout(kind="zen", detection_reason="validated_zen")
        return PackageLayout(kind="unknown", detection_reason="unknown")
