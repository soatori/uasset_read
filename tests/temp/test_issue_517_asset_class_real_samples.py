"""Opt-in public JSON acceptance coverage for #517 asset-class metadata."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from uasset_read import parse_single


_EXPECTED_JSON_EXPORTS = {
    "UASSET_READ_517_STATIC_MESH": {
        "root": ("SM_Rifle", "StaticMesh", "StaticMesh"),
        "child": ("BodySetup_1", "BodySetup", "StaticMesh"),
    },
    "UASSET_READ_517_SKELETAL_MESH": {
        "root": ("SKM_Rifle", "SkeletalMesh", "SkeletalMesh"),
        "child": (
            "FbxSkeletalMeshImportData_1",
            "FbxSkeletalMeshImportData",
            "SkeletalMesh",
        ),
    },
}


def _sample_path(variable: str) -> Path:
    configured = os.environ.get(variable)
    if not configured:
        pytest.skip(
            "set UASSET_READ_517_STATIC_MESH and UASSET_READ_517_SKELETAL_MESH "
            "to run the real-package acceptance checks"
        )
    path = Path(configured)
    assert path.is_file(), f"configured #517 sample is not a file: {path}"
    return path


@pytest.mark.parametrize("variable", sorted(_EXPECTED_JSON_EXPORTS))
def test_real_mesh_exports_keep_object_class_and_expose_asset_class(variable: str) -> None:
    sample = _sample_path(variable)
    payload = json.loads(
        parse_single(
            str(sample),
            format="json",
            force_full_parse=True,
            output_level="standard",
            log_enabled=False,
        )
    )
    exports = {export["object_name"]: export for export in payload["exports"]}

    for object_name, object_class, asset_class in _EXPECTED_JSON_EXPORTS[variable].values():
        rendered = exports[object_name]
        assert rendered["object_class"] == object_class
        assert rendered["asset_class"] == asset_class
