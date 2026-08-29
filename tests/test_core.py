"""Small permanent suite for stable cross-cutting contracts."""

from __future__ import annotations

from functools import lru_cache
import json
import logging
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(__file__).parent / "samples"
PACKAGE_SAMPLE = SAMPLES / "ABP_RifleAnimLayers.uasset"
DATA_SAMPLE = SAMPLES / "ALS_FootstepDataTable.uasset"
SCHEMA = ROOT / "docs/designs/contract/package_document_v2.schema.json"
EXAMPLE = ROOT / "docs/designs/contract/package_document_v2.example.json"


@lru_cache(maxsize=None)
def _document(sample: str = str(PACKAGE_SAMPLE), depth: str = "package"):
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(sample, depth=depth)


def test_reader_rejects_out_of_range_access():
    """A bounded reader must never escape its declared source region."""
    from uasset_read.v2.source import MemorySource, SliceReader

    source = MemorySource(b"0123456789")
    reader = SliceReader(source, 2, 5)
    assert reader.read(3) == b"234"
    assert reader.sub_slice(1, 2).read(2) == b"34"
    for operation in (lambda: source.read_at(-1, 1), lambda: reader.seek(6), lambda: reader.read(3)):
        with pytest.raises(IndexError):
            operation()


def test_package_document_preserves_every_export_and_role():
    """Package parsing must preserve every export, including packages without an asset role."""
    doc = _document()
    assert [obj.id for obj in doc.objects] == [f"export:{index}" for index in range(10)]
    assert len(doc.summary.asset_object_ids) == 2
    assert all(relation.from_id.startswith(("export:", "import:")) for relation in doc.relations)

    zero_role = _document(str(SAMPLES / "uasset_rs_UE410_SimpleRefsSoftRef.uasset"))
    assert len(zero_role.objects) == 6
    assert zero_role.summary.asset_object_ids == ()


def test_properties_are_bounded_and_opaque_bytes_are_not_embedded():
    """Selected properties must parse without exposing fallback bytes in JSON."""
    from uasset_read.models.fallback import FallbackReason, PropertyFallback
    from uasset_read.v2.api import parse_package_document
    from uasset_read.v2.properties import normalize_property_bag

    fallback = PropertyFallback(
        name="Mystery",
        type="UnknownProperty",
        size=4,
        raw_bytes=b"\x01\x02\x03\x04",
        reason=FallbackReason.UNSUPPORTED_TYPE,
    )
    assert normalize_property_bag([fallback])["Mystery"] == {
        "kind": "opaque",
        "type": "UnknownProperty",
        "size": 4,
        "reason": "unsupported_type",
    }

    doc = parse_package_document(PACKAGE_SAMPLE, depth="object", object_ids=["export:1"])
    assert doc.objects[1].properties
    json.dumps(doc.objects[1].properties)


def test_export_failure_keeps_the_rest_of_the_document():
    """A malformed export must produce an attributable diagnostic without deleting siblings."""
    doc = _document(depth="object")
    failures = [item for item in doc.diagnostics if item.code == "EXPORT_PROPERTY_PARSE_FAILED"]
    assert len(doc.objects) == 10
    assert len(doc.relations) > 0
    assert failures
    assert all(item.object_id and item.stage == "properties.tagged" for item in failures)
    assert not [item for item in doc.diagnostics if item.severity == "critical"]


def test_projection_honors_views_pagination_and_byte_budget():
    """Projection must keep view shape, continuation, and the final encoded byte limit coherent."""
    from uasset_read.v2.projection import project_document

    doc = _document()
    assert "flags" not in project_document(doc, view="semantic", limit=2)["objects"][0]
    assert "flags" in project_document(doc, view="raw", limit=2)["objects"][0]
    assert "debug" in project_document(doc, view="debug", limit=2)

    empty = project_document(doc, limit=0)
    budget = len(json.dumps(empty, separators=(",", ":")).encode()) + 2000
    page = project_document(doc, limit=100, max_bytes=budget)
    assert len(json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode()) <= budget
    assert page["next_offset"] > 0
    assert page["truncation"]["reason"] == "max_bytes"


def test_schema_accepts_the_example_and_all_public_views():
    """Checked examples and real public projections must satisfy the shipped JSON schema."""
    from uasset_read.v2.projection import project_document

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(json.loads(EXAMPLE.read_text(encoding="utf-8")), schema)
    for view in ("semantic", "raw", "debug"):
        jsonschema.validate(project_document(_document(), view=view, depth="asset", limit=2), schema)


def test_cli_python_and_agent_return_the_same_page():
    """All public entry points must project the same object IDs and diagnostics."""
    from uasset_read.v2.agent_tools import inspect_package
    from uasset_read.v2.projection import project_document

    expected = project_document(_document(str(DATA_SAMPLE)), depth="package", limit=2, max_bytes=4096)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uasset_read",
            "--v2",
            "--depth",
            "package",
            "--limit",
            "2",
            "--max-bytes",
            "4096",
            str(DATA_SAMPLE),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr[:500]
    for actual in (
        json.loads(result.stdout),
        inspect_package(str(DATA_SAMPLE), depth="package", limit=2, max_bytes=4096),
    ):
        assert [item["id"] for item in actual["objects"]] == [item["id"] for item in expected["objects"]]
        assert actual["diagnostics"] == expected["diagnostics"]


def test_library_parse_has_no_process_global_side_effects(tmp_path, monkeypatch):
    """Library parsing must not alter root logging or create files when logging is disabled."""
    handlers = tuple(logging.root.handlers)
    level = logging.root.level
    monkeypatch.chdir(tmp_path)
    _document(str(DATA_SAMPLE.resolve()))
    assert tuple(logging.root.handlers) == handlers
    assert logging.root.level == level
    assert list(tmp_path.iterdir()) == []


def test_projection_fields_filter_does_not_crash_and_scopes_payloads():
    """fields= must filter object fields without crashing payload/relation scoping."""
    from uasset_read.v2.projection import project_document

    doc = _document()
    result = project_document(doc, limit=2, fields=["class"])
    assert len(result["objects"]) == 2
    assert set(result["objects"][0]).issubset({"id", "name", "class"})
    assert isinstance(result["payloads"], list)
    assert isinstance(result["relations"], list)


def test_max_bytes_caps_final_output_including_truncation_block():
    """The final encoded projection must not exceed max_bytes once the truncation block is included."""
    from uasset_read.v2.projection import project_document

    doc = _document()
    empty = project_document(doc, limit=0)
    full = project_document(doc, limit=100)
    empty_size = len(json.dumps(empty, separators=(",", ":")).encode())
    full_size = len(json.dumps(full, separators=(",", ":")).encode())
    budget = (empty_size + full_size) // 2  # strictly between envelope and full page
    page = project_document(doc, limit=100, max_bytes=budget)
    final = len(json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode())
    assert final <= budget
    assert page["truncation"]["reason"] == "max_bytes"
