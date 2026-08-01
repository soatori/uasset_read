"""Opt-in real-package acceptance coverage for #514.

Set UASSET_READ_ICH_SAMPLE to a Blueprint package that contains an
InheritableComponentHandler export.  The UE 5.8 Vehicle template SportsCar
Blueprint is the recorded acceptance sample.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from uasset_read import parse_single
from uasset_read.core import parse_uasset_with_linker
from uasset_read.models.properties import StructValue


def _sample_path() -> Path:
    configured = os.environ.get("UASSET_READ_ICH_SAMPLE")
    if not configured:
        pytest.skip("set UASSET_READ_ICH_SAMPLE to run the real-package acceptance check")
    path = Path(configured)
    assert path.is_file(), f"configured #514 sample is not a file: {path}"
    return path


def test_real_inheritable_component_handler_records_are_tagged_properties() -> None:
    """A real Blueprint retains record identity and override references."""
    sample = _sample_path()
    result = parse_uasset_with_linker(
        str(sample),
        preload_all=True,
        force_full_parse=True,
    )
    linker = result.linker
    assert linker is not None

    matches = [
        (index, instance)
        for index, instance in enumerate(linker.export_objects())
        if instance.object_class == "InheritableComponentHandler"
    ]
    assert len(matches) == 1

    index, instance = matches[0]
    export = linker._export_map[index]
    assert getattr(instance, "fallback_reason", None) is None
    assert getattr(export, "parse_status", None) == "success"
    assert getattr(export, "fallback_reason", None) is None

    records_property = next(prop for prop in export.properties if prop.name == "Records")
    records = records_property.value
    assert len(records) == 4
    for record in records:
        assert isinstance(record, StructValue)
        assert record.struct_type == "ComponentOverrideRecord"
        assert record.parse_status == "success"
        assert {"ComponentClass", "ComponentTemplate", "ComponentKey"} <= record.fields.keys()
        component_key = record.fields["ComponentKey"]
        assert isinstance(component_key, StructValue)
        assert component_key.fields["SCSVariableName"]
        assert "AssociatedGuid" in component_key.fields

    payload = json.loads(parse_single(
        str(sample),
        format="json",
        force_full_parse=True,
        output_level="standard",
        log_enabled=False,
    ))
    rendered = [
        item for item in payload["exports"]
        if item["object_class"] == "InheritableComponentHandler"
    ]
    assert len(rendered) == 1
    assert "parse_status" not in rendered[0]
    assert "fallback_reason" not in rendered[0]
    rendered_records = next(
        prop for prop in rendered[0]["properties"] if prop["name"] == "Records"
    )["value"]
    assert len(rendered_records) == 4
    assert {
        "ComponentClass", "ComponentTemplate", "ComponentKey",
    } <= rendered_records[0]["fields"].keys()
