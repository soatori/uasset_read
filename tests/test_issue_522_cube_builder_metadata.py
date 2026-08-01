"""Regression coverage for #522's CubeBuilder property metadata path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from uasset_read import parse_single
from uasset_read.parsers.asset_types.property_metadata import build_property_metadata
from uasset_read.parsers.class_serialization_strategy import (
    SerializationStrategy,
    get_serialization_strategy,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "samples" / "FirstPerson_Lvl_FirstPerson.umap"
SOURCE_FIXTURE_SHA256 = (
    "3D476154BF4CAC39A59EC91B88F5ED6889AF113A1ECF9690A01C89D8BC32D258"
)


def test_public_map_exposes_cube_builder_property_metadata() -> None:
    """CubeBuilder properties are published without decoding its native payload."""
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper() == SOURCE_FIXTURE_SHA256

    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))
    cube = next(export for export in payload["exports"] if export["object_name"] == "CubeBuilder_3")

    assert payload["status"]["status"] == "partial"
    assert cube["parse_status"] == "partial_metadata"
    metadata = cube["asset_type_data"]
    assert metadata["asset_type"] == "CubeBuilder"
    assert metadata["parse_status"] == "partial_metadata"
    assert metadata["layer"] == "Cube"
    assert metadata["polygon_count"] == 6
    assert metadata["vertex_payload_size"] == 196


def test_empty_cube_builder_metadata_remains_opaque() -> None:
    """No serialized business fields must not imply partial extraction."""
    assert build_property_metadata("CubeBuilder", []) == {
        "asset_type": "CubeBuilder",
        "parse_status": "opaque",
    }


def test_cube_builder_uses_opaque_strategy_without_broadening_skip_prefixes() -> None:
    """Only the exact CubeBuilder class is reclassified from the builder skip family."""
    assert get_serialization_strategy("CubeBuilder") is SerializationStrategy.OPAQUE_CLASS_PAYLOAD
    assert get_serialization_strategy("GeomModifier_Any") is SerializationStrategy.SKIP_UNSUPPORTED
    assert get_serialization_strategy("BrushBuilderAny") is SerializationStrategy.SKIP_UNSUPPORTED
