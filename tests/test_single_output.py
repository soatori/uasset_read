# tests/test_single_output.py
"""Single-output writer: one deterministic UTF-8 JSON document per package."""

import json

from tests.fixtures import parse_sample
from uasset_read.projection import project_document
from uasset_read.projections.bundle import write_projected_document
from uasset_read.projections.registry import ProjectorRegistry


def test_projections_are_embedded_and_have_no_default_output_paths():
    table = parse_sample("FirstPerson_DT_WeaponList.uasset", depth="decode")
    projections = ProjectorRegistry.default().project_document(table)
    assert projections
    assert all(item.embedded for item in projections)
    assert all(item.content is not None or item.status == "unavailable" for item in projections)


def test_single_document_writer_matches_the_project_document_dict(document, tmp_path):
    output = write_projected_document(document, tmp_path / "Asset.json")
    assert output.name == "Asset.json"
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == project_document(document)
    assert payload["mode"] == "normal"


def test_writer_debug_mode_matches_the_debug_projection(document, tmp_path):
    output = write_projected_document(document, tmp_path / "Debug.json", mode="debug")
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == project_document(document, mode="debug")


def test_writer_is_deterministic(document, tmp_path):
    first = write_projected_document(document, tmp_path / "A.json")
    second = write_projected_document(document, tmp_path / "B.json")
    assert first.read_bytes() == second.read_bytes()
