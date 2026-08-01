"""Opt-in real-package acceptance coverage for #515 EditedDocumentInfo."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest

from uasset_read import parse_single
from uasset_read.core import parse_uasset_with_linker
from uasset_read.models.properties import StructValue


_EXPECTED_SUB_PATHS = [
    "UserConstructionScript",
    "EventGraph",
]
_EXPECTED_ZOOMS = [0.75, 1.0]
_EXPECTED_EXPORT_NAME = "BP_VehicleAdvSportsCar"
_EXPECTED_ASSET_PATH_SUFFIX = ".BP_VehicleAdvSportsCar"


def _sample_path() -> Path:
    configured = os.environ.get("UASSET_READ_EDI_SAMPLE")
    if not configured:
        pytest.skip(
            "set UASSET_READ_EDI_SAMPLE to the UE 5.8 BP_VehicleAdvSportsCar package"
        )
    path = Path(configured)
    assert path.is_file(), f"configured #515 sample is not a file: {path}"
    return path


def _last_edited_documents(export) -> list[StructValue]:
    property_value = next(
        prop.value
        for prop in export.properties
        if prop.name == "LastEditedDocuments"
    )
    assert isinstance(property_value, list)
    return property_value


def _assert_document_fields(record, index: int) -> None:
    path_value = record["EditedObjectPath"]
    offset_value = record["SavedViewOffset"]

    assert path_value["kind"] == "struct_binary_decoded"
    assert path_value["struct_type"] == "SoftObjectPath"
    assert path_value["size"] == 4
    assert path_value["fields"]["index"] == index
    assert path_value["fields"]["sub_path"] == _EXPECTED_SUB_PATHS[index]
    assert path_value["fields"]["asset_path"].endswith(_EXPECTED_ASSET_PATH_SUFFIX)
    assert "raw_data" not in path_value

    assert offset_value["kind"] == "struct_binary_decoded"
    assert offset_value["struct_type"] == "DeprecateSlateVector2D"
    assert offset_value["size"] == 8
    assert set(offset_value["fields"]) == {"X", "Y"}
    assert all(math.isfinite(offset_value["fields"][axis]) for axis in ("X", "Y"))
    assert "raw_data" not in offset_value


def test_real_ue58_edited_document_info_records_are_fully_decoded() -> None:
    """The recorded UE 5.8 Blueprint exposes its editor document records."""
    sample = _sample_path()
    result = parse_uasset_with_linker(
        str(sample),
        preload_all=True,
        force_full_parse=True,
    )
    assert result.is_success
    engine_version = result.summary.saved_by_engine_version
    assert (engine_version.major, engine_version.minor) == (5, 8)
    assert engine_version.branch == "++UE5+Dev-Release-5.8"

    export = next(
        export
        for export in result.export_map
        if export.object_name == _EXPECTED_EXPORT_NAME
    )
    records = _last_edited_documents(export)
    assert len(records) == 2

    for index, record in enumerate(records):
        assert isinstance(record, StructValue)
        assert record.struct_type == "EditedDocumentInfo"
        assert record.parse_status == "success"
        assert set(record.fields) == {
            "EditedObjectPath",
            "SavedViewOffset",
            "SavedZoomAmount",
        }
        _assert_document_fields(record.fields, index)
        assert record.fields["SavedZoomAmount"] == _EXPECTED_ZOOMS[index]

    payload = json.loads(
        parse_single(
            str(sample),
            format="json",
            force_full_parse=True,
            output_level="standard",
            log_enabled=False,
        )
    )
    rendered_export = next(
        export
        for export in payload["exports"]
        if export["object_name"] == _EXPECTED_EXPORT_NAME
    )
    rendered_records = next(
        prop for prop in rendered_export["properties"]
        if prop["name"] == "LastEditedDocuments"
    )["value"]
    assert len(rendered_records) == 2

    for index, record in enumerate(rendered_records):
        assert record["struct_type"] == "EditedDocumentInfo"
        assert set(record["fields"]) == {
            "EditedObjectPath",
            "SavedViewOffset",
            "SavedZoomAmount",
        }
        _assert_document_fields(record["fields"], index)
        assert record["fields"]["SavedZoomAmount"] == _EXPECTED_ZOOMS[index]
