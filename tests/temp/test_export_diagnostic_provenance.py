"""Regression coverage for export-table structured diagnostic provenance."""

from __future__ import annotations

import pytest

from uasset_read.constants import (
    UE4_64BIT_EXPORTMAP_SERIALSIZES,
    UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID,
)
from uasset_read.serializers.object_resources import read_export_map
from uasset_read.serializers.package_summary import PackageFileSummary


class _ExportMapArchive:
    """Narrow archive fake that records the exact export-table read offsets."""

    def __init__(self) -> None:
        self.position = 0
        self.structured_diagnostics: list[dict] = []

    def seek(self, position: int) -> None:
        self.position = position

    def tell(self) -> int:
        return self.position

    def read_i32(self, key: str = "") -> int:
        self.position += 4
        if key.endswith("SerialSize") or key.endswith("SerialOffset"):
            return -1
        return 0

    def read_i64(self, key: str = "") -> int:
        self.position += 8
        if key.endswith("SerialSize") or key.endswith("SerialOffset"):
            return -1
        return 0

    def read_u32(self, key: str = "") -> int:
        self.position += 4
        return 0

    def read_bool(self, key: str = "") -> bool:
        self.position += 4
        return False

    def read_name(self, name_map: list[str], key: str = "") -> str:
        self.position += 8
        return "ExportObject"

    def read(self, size: int) -> bytes:
        self.position += size
        return b"\0" * size

    def _record_structured_diagnostic(self, **kwargs) -> None:
        self.structured_diagnostics.append(kwargs)


@pytest.mark.parametrize(
    ("file_version_ue4", "expected_offsets"),
    [
        (UE4_64BIT_EXPORTMAP_SERIALSIZES - 1, [1028, 1032]),
        (UE4_64BIT_EXPORTMAP_SERIALSIZES, [1028, 1036]),
    ],
    ids=["pre_64_bit_i32", "64_bit_i64"],
)
def test_negative_serial_fields_keep_distinct_codes_and_exact_offsets(
    file_version_ue4: int,
    expected_offsets: list[int],
) -> None:
    archive = _ExportMapArchive()
    summary = PackageFileSummary(
        tag=0,
        legacy_file_version=0,
        file_version_ue4=file_version_ue4,
        file_version_ue5=UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID,
        export_count=1,
        export_offset=1000,
    )

    exports = read_export_map(archive, summary, [])

    assert len(exports) == 1
    assert [diagnostic["code"] for diagnostic in archive.structured_diagnostics] == [
        "invalid_serial_size",
        "invalid_serial_offset",
    ]
    assert [diagnostic["offset"] for diagnostic in archive.structured_diagnostics] == expected_offsets
