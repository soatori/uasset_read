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
    # View shape: semantic omits flags, raw includes them
    assert "flags" not in project_document(doc, view="semantic", limit=2)["objects"][0]
    assert "flags" in project_document(doc, view="raw", limit=2)["objects"][0]
    assert "debug" in project_document(doc, view="debug", limit=2)

    # Pagination and byte budget
    full = project_document(doc, limit=100)
    full_size = len(json.dumps(full, separators=(",", ":")).encode())
    # budget must exceed minimal reachable envelope (depends_on imports)
    # but be less than the full page to trigger truncation
    budget = full_size - 1000
    page = project_document(doc, limit=100, max_bytes=budget)
    assert len(json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode()) <= budget
    assert page["next_offset"] > 0
    assert page["truncation"]["reason"] == "max_bytes"

    # fields filter: only requested fields plus id/name are returned
    result = project_document(doc, limit=2, fields=["id"])
    assert len(result["objects"]) == 2
    assert set(result["objects"][0].keys()).issubset({"id", "name"})
    assert isinstance(result["payloads"], list)
    assert isinstance(result["relations"], list)


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
    full = project_document(doc, limit=100)
    full_size = len(json.dumps(full, separators=(",", ":")).encode())
    budget = full_size - 1000  # strictly less than full page
    page = project_document(doc, limit=100, max_bytes=budget)
    final = len(json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode())
    assert final <= budget
    assert page["truncation"]["reason"] == "max_bytes"
    assert page["next_offset"] > 0


def _synthetic_export(**kwargs):
    from uasset_read.serializers.object_resources import ObjectExport, PackageIndex

    base = dict(
        class_index=PackageIndex(-1),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="Test",
        object_flags=0,
        serial_size=0,
        serial_offset=0,
    )
    base.update(kwargs)
    return ObjectExport(**base)


def test_preload_relations_use_ue_ranges_and_sign_semantics():
    """Per-export preload ranges index the flat summary array; sign maps like FPackageIndex."""
    from uasset_read.v2.package.legacy import _build_preload_relations

    exports = [
        _synthetic_export(
            first_export_dependency=0,
            serialization_before_serialization_dependencies=2,
            create_before_create_dependencies=1,
        ),
        _synthetic_export(first_export_dependency=-1),
        _synthetic_export(
            first_export_dependency=3,
            serialization_before_serialization_dependencies=2,
        ),
    ]
    # raw values: +2 -> export:1, -4 -> import:3, 0 -> null, -1 -> import:0, +1 -> export:0
    preload = [2, -4, 0, -1, 1]

    relations, diagnostics = _build_preload_relations(preload, exports)
    edges = {(r.kind, r.from_id, r.to_id) for r in relations}
    assert edges == {
        ("preload_of", "export:0", "export:1"),
        ("preload_of", "export:0", "import:3"),
        ("preload_of", "export:2", "import:0"),
        ("preload_of", "export:2", "export:0"),
    }
    assert diagnostics == []


def test_relation_targets_out_of_range_are_dropped_with_diagnostic():
    """A relation whose target exceeds the table size is corrupt data, not an edge."""
    from uasset_read.v2.object_model import Relation
    from uasset_read.v2.package.legacy import _validate_relation_targets

    relations = [
        Relation(kind="outer_of", from_id="export:0", to_id="export:1"),
        Relation(kind="outer_of", from_id="export:1", to_id="export:67108864"),
        Relation(kind="class_of", from_id="export:2", to_id="import:5"),
        Relation(kind="class_of", from_id="export:3", to_id="import:999"),
    ]
    kept, diagnostics = _validate_relation_targets(relations, export_count=2, import_count=6)
    assert [(r.kind, r.from_id, r.to_id) for r in kept] == [
        ("outer_of", "export:0", "export:1"),
        ("class_of", "export:2", "import:5"),
    ]
    assert len(diagnostics) == 2
    assert {d.code for d in diagnostics} == {"RELATION_TARGET_OUT_OF_RANGE"}
    assert {d.object_id for d in diagnostics} == {"export:1", "export:3"}
    assert all(d.recoverable for d in diagnostics)


def test_depends_map_validates_package_index_sign_per_ue_convention():
    """read_depends_map must range-check positives against exports, negatives against imports."""

    class _StubArchive:
        def __init__(self, values):
            self._values = list(values)
            self._pos = 0

        def seek(self, offset):
            self._pos = 0

        def read_i32(self, context):
            value = self._values[self._pos]
            self._pos += 1
            return value

    from types import SimpleNamespace

    from uasset_read.serializers.package_summary import read_depends_map

    summary = SimpleNamespace(depends_offset=1, export_count=3, import_count=5)
    # export 0 list: +2 -> export:1 (valid), -2 -> import:1 (valid),
    # +4 -> export:3 (missing, export_count=3), -99 -> import:98 (missing)
    archive = _StubArchive([4, 2, -2, 4, -99, 0, 0])
    warnings: list[str] = []
    result = read_depends_map(archive, summary, warnings=warnings)
    assert result == [[2, -2, 4, -99], [], []]
    invalid = [w for w in warnings if "non-existent" in w]
    assert len(invalid) == 1
    assert "2 PackageIndex value(s)" in invalid[0]


def test_preload_relations_report_invalid_ranges_without_crashing():
    """Out-of-range preload spans produce a structured diagnostic and are skipped."""
    from uasset_read.v2.package.legacy import _build_preload_relations

    exports = [
        _synthetic_export(
            first_export_dependency=2,
            serialization_before_serialization_dependencies=5,
        ),
        _synthetic_export(
            first_export_dependency=0,
            serialization_before_serialization_dependencies=1,
        ),
    ]
    relations, diagnostics = _build_preload_relations([3, -2], exports)
    assert [(r.from_id, r.to_id) for r in relations] == [("export:1", "export:2")]
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "PRELOAD_DEPENDENCY_RANGE_INVALID"
    assert diagnostics[0].object_id == "export:0"
    assert diagnostics[0].recoverable is True
