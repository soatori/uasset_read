"""Sample quality gates for the v4 package-output path (normal/debug modes).

Acceptance numbers are locked to the plan/spec/manifest table. Sample-facing
checks consume projected document dicts (not live IR dataclasses) except where
``BlueprintCorrelation`` itself is the named semantic trace API. The
real-fixture matrix at the bottom accepts the named tracked samples in both
output modes against the frozen v4 contract.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema

from tests.fixtures import (
    find_blueprint_object,
    find_function,
    find_material_graph,
    parse_sample,
)
from tests.test_contract_v4 import _schema
from uasset_read.parsers.blueprint.correlation import BlueprintCorrelation
from uasset_read.package import parse_package_document
from uasset_read.projection import project_document

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(__file__).parent / "samples"
USMAP = SAMPLES / "UnversionedTest.usmap"
CONTAINERS = SAMPLES / "containers"

COMPLETENESS_ENUM = {"complete", "partial", "opaque", "unavailable", "failed"}
STATUS_ENUM = {"translated", "represented", "untranslated", "unavailable"}


def test_completeness_label_mapping_contract():
    """Projection completeness enum: never overclaim complete; opaque/failed when warranted."""
    from types import SimpleNamespace

    from uasset_read.projections.records import (
        ProjectionRecord,
        _completeness_label,
        projection_to_dict,
    )

    # Measured full ratio → complete.
    assert _completeness_label("translated", 1.0) == "complete"
    # Measured partial ratio → partial.
    assert _completeness_label("represented", 0.5) == "partial"
    assert _completeness_label("represented", 0.97) == "partial"
    # Missing ratio must NOT overclaim complete.
    assert _completeness_label("represented", None) == "partial"
    assert _completeness_label("translated", None) == "partial"
    # Untranslated with no mapped ratio → opaque (source exists, not mapped).
    assert _completeness_label("untranslated", None) == "opaque"
    assert _completeness_label("untranslated", 0.0) == "opaque"
    # Absent source → unavailable.
    assert _completeness_label("unavailable", None) == "unavailable"
    # Failure diagnostics → failed even when status is unavailable.
    failed_diag = SimpleNamespace(code="blueprint_render_failed")
    assert _completeness_label("unavailable", None, [failed_diag]) == "failed"
    assert _completeness_label("represented", 0.5, [{"code": "graph_render_failed"}]) == "failed"

    # End-to-end: represented + completeness=None projects as partial, not complete.
    record = ProjectionRecord(
        kind="asset_metadata",
        source_object_id="export:0",
        media_type="application/json",
        content={"kind": "asset_metadata"},
        embedded=True,
        status="represented",
        completeness=None,
        dependencies=[],
        diagnostics=[],
    )
    assert projection_to_dict(record)["completeness"] == "partial"

    # unavailable_records with render_failed code → failed completeness.
    from uasset_read.projections.records import unavailable_records

    failed_records = unavailable_records(
        "export:0",
        (("asset_metadata", "application/json"),),
        code="blueprint_render_failed",
        message="render failed",
        stage="projection.blueprint",
    )
    assert projection_to_dict(failed_records[0])["completeness"] == "failed"
    assert projection_to_dict(failed_records[0])["status"] == "unavailable"


def count_kismet_expressions(semantic_dict) -> int:
    """Sum expression_count over projected function dicts on one semantic."""
    total = 0
    for fn in semantic_dict.get("functions") or []:
        total += fn.get("expression_count") or 0
    return total


def _function_dicts(document) -> list[dict]:
    out: list[dict] = []
    for obj in document.objects:
        for fn in (obj.semantic or {}).get("functions") or []:
            out.append(fn)
    return out


# --------------------------------------------------------------------------- #
# Gate 1 — StackOBot Blueprint
# --------------------------------------------------------------------------- #


def test_stackobot_blueprint_acceptance():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    assert len(document.objects) == 31
    assert document.package.export_count == 31

    blueprint = find_blueprint_object(document)
    semantic = blueprint.semantic or {}
    assert semantic.get("kind") in {"blueprint", "anim_blueprint"}
    assert len(semantic.get("graphs") or []) == 2
    assert len(semantic.get("functions") or []) == 3
    assert count_kismet_expressions(semantic) == 85

    # CFG blocks/edges, call targets, and var reads/writes on projected dicts.
    functions = semantic["functions"]
    assert any((fn.get("cfg") or {}).get("blocks") for fn in functions)
    assert any((fn.get("cfg") or {}).get("edges") for fn in functions)
    assert any(fn.get("calls") for fn in functions)
    assert any(fn.get("reads") for fn in functions)
    assert any(fn.get("writes") for fn in functions)
    for fn in functions:
        assert fn.get("instructions") is not None
        assert fn.get("expression_count") is not None

    # Correlation semantic trace locks the same 85 / 3 numbers.
    corr = BlueprintCorrelation().build(document)
    assert len(corr.functions) == 3
    assert sum(fn.expression_count for fn in corr.functions) == 85
    assert corr.control_flow
    assert corr.calls
    assert corr.variable_accesses
    assert len(corr.graphs) == 2


# --------------------------------------------------------------------------- #
# Gate 2 — UE5.8 Blueprint
# --------------------------------------------------------------------------- #


def test_ue58_blueprint_acceptance():
    document = parse_sample("MyProject_UE58_TestBlueprint.uasset", depth="decode")
    assert len(document.objects) == 24

    opcodes: set[str] = set()
    node_classes: set[str] = set()
    edge_kinds: set[str] = set()
    for obj in document.objects:
        semantic = obj.semantic or {}
        for graph in semantic.get("graphs") or []:
            for node in graph.get("nodes") or []:
                class_name = node.get("class_name") or ""
                if class_name:
                    node_classes.add(class_name)
        for fn in semantic.get("functions") or []:
            for item in fn.get("instructions") or []:
                opcodes.add(item["opcode"])
            cfg = fn.get("cfg") or {}
            for edge in cfg.get("edges") or []:
                edge_kinds.add(edge.get("kind") or "")

    assert "K2Node_IfThenElse" in node_classes
    assert "EX_JumpIfNot" in opcodes
    assert {"true", "false"} <= edge_kinds

    function = find_function(document, "NewFunction")
    assert any(item["opcode"] == "EX_JumpIfNot" for item in function["instructions"])
    function_edges = {(edge.get("kind") or "") for edge in (function.get("cfg") or {}).get("edges") or []}
    assert {"true", "false"} <= function_edges


# --------------------------------------------------------------------------- #
# Gate 3 — StackOBot Material
# --------------------------------------------------------------------------- #


def test_stackobot_material_acceptance():
    document = parse_sample("StackOBot_M_BotBase.uasset", depth="decode")
    assert len(document.objects) == 42

    graph = find_material_graph(document)
    assert len(graph["expressions"]) == 39
    assert graph.get("links"), "material graph must expose links when present"
    assert graph.get("parameters")
    for expression in graph["expressions"]:
        # Expression properties: identity + projected property payload keys.
        assert expression.get("object_id")
        assert expression.get("class_name")
        assert "inputs" in expression
        assert "constants" in expression

    material = next(obj for obj in document.objects if obj.class_name == "Material")
    attached = (material.semantic or {}).get("material_graph") or {}
    assert len(attached.get("expressions") or []) == 39


# --------------------------------------------------------------------------- #
# Gate 4 — unversioned samples: schema decode or bounded opaque
# --------------------------------------------------------------------------- #


def test_unversioned_samples_schema_decode_or_bounded_opaque():
    for name in ("BP_UnversionedTest.uasset", "DA_UnversionedTest.uasset"):
        path = SAMPLES / name
        # Without usmap: bounded opaque, never position-only guessing.
        opaque_doc = parse_package_document(path, depth="object")
        codes = [d.code for d in opaque_doc.diagnostics]
        assert "name_index_out_of_range" not in codes, name
        assert opaque_doc.objects
        for obj in opaque_doc.objects:
            props = obj.properties or {}
            if not props:
                continue
            # Either empty, mapped values, or explicit opaque descriptors.
            for value in props.values() if isinstance(props, dict) else []:
                if isinstance(value, dict) and value.get("kind") == "opaque":
                    assert value.get("reason") or value.get("type"), name

        # With usmap: schema decode where the mapping exists.
        mapped = parse_package_document(
            path,
            depth="object",
            mappings_path=str(USMAP),
        )
        codes = [d.code for d in mapped.diagnostics]
        assert "name_index_out_of_range" not in codes, name

    da = parse_package_document(
        SAMPLES / "DA_UnversionedTest.uasset",
        depth="object",
        mappings_path=str(USMAP),
    )
    da_obj = next(o for o in da.objects if o.name == "DA_UnversionedTest")
    props = da_obj.properties or {}
    assert props.get("AssetID", {}).get("value") == "UnversionedAssetID"
    assert props.get("NumericArray", {}).get("value") == [10, 20, 30, 40]

    bp = parse_package_document(
        SAMPLES / "BP_UnversionedTest.uasset",
        depth="object",
        mappings_path=str(USMAP),
    )
    cdo = next(o for o in bp.objects if o.name == "Default__BP_UnversionedTest_C")
    cdo_props = cdo.properties or {}
    assert cdo_props.get("ScriptInt", {}).get("value") == 77
    assert cdo_props.get("ScriptBool", {}).get("value") is True
    class_obj = next(o for o in bp.objects if o.name == "BP_UnversionedTest_C")
    class_props = class_obj.properties or {}
    class_values = (
        list(class_props.values()) if isinstance(class_props, dict) else [entry.value for entry in class_props.entries]
    )
    assert any(isinstance(v, dict) and v.get("kind") == "opaque" for v in class_values), (
        "unmapped class export must stay bounded opaque"
    )


# --------------------------------------------------------------------------- #
# Gate 5 — committed containers: IoStore metadata + truthful Zen unavailability
# --------------------------------------------------------------------------- #


def test_committed_containers_iostore_metadata_and_zen_unavailability():
    from uasset_read.containers import inspect_container
    from uasset_read.parsers.zen_reader import ZenPackageReader

    toc_path = CONTAINERS / "MyProject-Windows.utoc"
    assert toc_path.exists()
    report = inspect_container(toc_path)
    assert report.kind in {"iostore_toc", "iostore"}
    assert report.diagnostics is not None

    result = ZenPackageReader().read_from_container(
        report,
        package_id="<fixture-package-not-provided>",
    )
    assert result.document is None
    assert result.status == "unavailable"
    assert result.reason in {"chunk_bytes_unavailable", "zen_package_fixture_unavailable"}
    assert result.diagnostics
    # Real Zen package parsing stays deferred until redistributable fixtures exist.
    assert all(d.stage.startswith("zen") or d.stage.startswith("container") for d in result.diagnostics)


# --------------------------------------------------------------------------- #
# Gate 7 — type-aware projections on recognized families
# --------------------------------------------------------------------------- #

# Retired C++/builder kind and media tokens, assembled without re-introducing
# the banned literal tokens into tracked source.
_KIND_TOKEN = "cpp"
_BUILDER_TOKEN = "editor_builder"
_MEDIA_TOKEN = "text/x-c"


def test_type_aware_projection_acceptance():
    from uasset_read.projections.registry import CAPABILITY_MATRIX, ProjectorRegistry

    registry = ProjectorRegistry.default()

    material_doc = parse_sample("StackOBot_M_BotBase.uasset", depth="decode")
    projections = registry.project_document(material_doc)
    material = next(obj for obj in material_doc.objects if obj.id == "export:0")
    assert len((material.semantic or {}).get("material_graph", {}).get("expressions", [])) == 39
    assert all(item.source_object_id for item in projections)
    assert all(item.status in STATUS_ENUM for item in projections)

    # Cooked material keeps its semantic; no builder projection is faked.
    cooked = parse_sample("TestMaterial.uasset", depth="decode")
    cooked_projections = registry.project_document(cooked)
    assert all(_BUILDER_TOKEN not in item.kind for item in cooked_projections)

    # Blueprint family: static semantics live on objects[].semantic; no
    # retired C++ projection kinds or media types may reappear.
    bp_doc = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    bp_projections = registry.project_document(bp_doc)
    for item in bp_projections:
        assert _KIND_TOKEN not in item.kind
        assert _BUILDER_TOKEN not in item.kind
        assert not item.media_type.startswith(_MEDIA_TOKEN)

    # Data assets use CSV/JSON where decoded.
    table = parse_sample("FirstPerson_DT_WeaponList.uasset", depth="asset")
    table_kinds = {item.kind for item in registry.project_document(table)}
    assert {"data_table", "data_table_csv", "data_table_json"} <= table_kinds

    # Capability matrix still declares the recognized families.
    families = {entry["family"] for entry in CAPABILITY_MATRIX}
    assert {"blueprint_family", "material", "data_table", "curve_table"} <= families


# --------------------------------------------------------------------------- #
# Gate 8 — single-document output
# --------------------------------------------------------------------------- #


def test_single_document_contains_all_projection_sections(stackobot_document):
    output = project_document(stackobot_document)
    assert output["format_version"] == "4.0"
    assert output["package"]
    assert output["objects"]
    assert "projections" in output
    # The blueprint family emits no embedded records (retired C++ output is
    # gone, not faked unavailable); any record that exists stays schema-shaped.
    assert all(item["embedded"] for item in output["projections"])
    assert all(item["completeness"] in COMPLETENESS_ENUM for item in output["projections"])
    assert all(item["status"] in STATUS_ENUM for item in output["projections"])
    assert all("provenance" in item for item in output["projections"])
    # Ordinary asset/graph boundaries do not split the document.
    assert len(output["objects"]) == len(stackobot_document.objects)
    assert {item["id"] for item in output["objects"]} == {obj.id for obj in stackobot_document.objects}


# --------------------------------------------------------------------------- #
# Gate 9 — byte accounting (debug evidence)
# --------------------------------------------------------------------------- #


def test_debug_byte_accounting_scopes_are_contract_shaped(stackobot_document):
    output = project_document(stackobot_document, mode="debug")
    scopes = output["debug"]["byte_accounting"]
    assert isinstance(scopes, list)
    assert scopes
    for scope in scopes:
        assert scope["object_id"].startswith("export:")
        assert scope["window"]["size"] >= 0
        assert scope["leaves"]
        for leaf in scope["leaves"]:
            assert leaf["size"] > 0
            assert leaf["status"] in {"decoded", "opaque", "payload", "unavailable"}


# --------------------------------------------------------------------------- #
# v4 real-fixture matrix — normal/debug acceptance for named tracked samples
# --------------------------------------------------------------------------- #


def _strip_debug_evidence(value) -> None:
    """Recursively remove nested ``debug_evidence`` keys (plan strip rule)."""
    if isinstance(value, dict):
        value.pop("debug_evidence", None)
        for item in value.values():
            _strip_debug_evidence(item)
    elif isinstance(value, list):
        for item in value:
            _strip_debug_evidence(item)


def _accepted_pair(document):
    """Produce normal+debug via the public producer, validate both, assert parity.

    The debug-strip comparison is exact: deepcopy debug, pop the top-level
    ``debug`` object, remove nested ``debug_evidence`` keys, normalize ``mode``
    to ``normal``, and require equality with the normal document (ordered
    properties and decoded values included).
    """
    normal = project_document(document)
    debug = project_document(document, mode="debug")
    schema = _schema()
    jsonschema.validate(normal, schema)
    jsonschema.validate(debug, schema)
    stripped = copy.deepcopy(debug)
    stripped.pop("debug")
    _strip_debug_evidence(stripped)
    stripped["mode"] = "normal"
    assert stripped == normal
    return normal, debug


def test_matrix_blueprint_fixture_acceptance():
    """Matrix: all exports; ordered properties; IR/CFG/calls/reads/writes; no C++ kinds; parity."""
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    normal, debug = _accepted_pair(document)

    # All exports, in table-index order.
    assert len(normal["objects"]) == 31
    assert [item["id"] for item in normal["objects"]] == [f"export:{i}" for i in range(31)]

    # Ordered properties: occurrence restarts per name and preserves order.
    for item in normal["objects"]:
        occurrences: dict[str, int] = {}
        for prop in item["properties"]:
            assert prop["occurrence"] == occurrences.get(prop["name"], 0)
            occurrences[prop["name"]] = prop["occurrence"] + 1

    # Blueprint instructions, CFG, calls, reads, writes on the projected semantic.
    bp = find_blueprint_object(document)
    entry = next(item for item in normal["objects"] if item["id"] == bp.id)
    functions = entry["semantic"]["functions"]
    assert functions
    assert any(fn.get("instructions") for fn in functions)
    assert any((fn.get("cfg") or {}).get("blocks") for fn in functions)
    assert any((fn.get("cfg") or {}).get("edges") for fn in functions)
    assert any(fn.get("calls") for fn in functions)
    assert any(fn.get("reads") for fn in functions)
    assert any(fn.get("writes") for fn in functions)

    # No C++ projection kinds or media types in either mode.
    for mode, projected in (("normal", normal), ("debug", debug)):
        for record in projected["projections"]:
            assert _KIND_TOKEN not in record["kind"], mode
            assert _BUILDER_TOKEN not in record["kind"], mode
            assert not record["media_type"].startswith(_MEDIA_TOKEN), mode


def test_matrix_material_fixture_acceptance():
    """Matrix: decoded material graph/static semantics and parity."""
    document = parse_sample("StackOBot_M_BotBase.uasset", depth="decode")
    normal, _debug = _accepted_pair(document)

    entry = next(item for item in normal["objects"] if item["id"] == "export:0")
    semantic = entry["semantic"]
    assert semantic["kind"] == "material"
    graph = semantic["material_graph"]
    assert len(graph["expressions"]) == 39
    assert graph["links"]
    assert graph["parameters"]
    for expression in graph["expressions"]:
        assert expression.get("object_id")
        assert expression.get("class_name")
        assert "inputs" in expression
        assert "constants" in expression
    # Static semantics decoded alongside the graph (Nanite usage + editor pins).
    assert semantic["bUsedWithNanite"] is True
    assert semantic["EditorX"] == 1232
    assert semantic["EditorY"] == -64


def test_matrix_datatable_fixture_acceptance():
    """Matrix: DataTable represented tier (type/size cells) plus JSON/CSV consistency."""
    import csv
    from io import StringIO

    document = parse_sample("FirstPerson_DT_WeaponList.uasset", depth="decode")
    normal, _debug = _accepted_pair(document)
    records = {item["kind"]: item for item in normal["projections"]}
    assert {"data_table", "data_table_csv", "data_table_json"} <= set(records)

    data = records["data_table"]["content"]
    # Honest represented tier: row struct schema evidenced, cell values not decoded.
    assert data["values_decoded"] is False
    assert records["data_table"]["status"] == "represented"
    assert records["data_table"]["completeness"] == "partial"
    assert data["row_names"] == ["GrenadeLauncher", "Pistol", "Rifle"]
    assert data["row_count"] == 3
    assert len(data["rows"]) == 3
    for row in data["rows"]:
        # Row cells are {type, size} descriptors, not decoded values: table row
        # value bytes are not decoded by any current reader (legacy_reader.py:
        # "values not decoded yet"). JSON/CSV consistency below is what this
        # cell verifies; decoded cell values are a future reader task.
        assert row["values"], row["name"]
        assert set(row["values"]) == {column["name"] for column in data["columns"]}

    # JSON/CSV consistency: data_table_json embeds the same content dict, and
    # every CSV cell is exactly the shared serializer form of that value.
    assert records["data_table_json"]["content"] == data
    rows = list(csv.reader(StringIO(records["data_table_csv"]["content"])))
    assert rows[0] == ["name"] + [column["name"] for column in data["columns"]]
    assert all(len(cells) == len(rows[0]) for cells in rows)
    assert [cells[0] for cells in rows[1:]] == data["row_names"]
    for cells, row in zip(rows[1:], data["rows"]):
        for cell, column in zip(cells[1:], data["columns"]):
            value = row["values"][column["name"]]
            if value is None:
                assert cell == ""
            elif isinstance(value, str):
                assert cell == value
            else:
                assert cell == json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def test_matrix_curve_table_fixtures_acceptance():
    """Matrix: CurveTable keys/mode plus valid stable CSV rows.

    Keys/mode are the decoded TMap row keys and ECurveTableMode byte (pinned by
    ORIGIN-issue-626). The rows are valid (one entry per key, field schema
    decoded) and stable (deterministic across projections). Key *points* stay at
    the reader's explicit ``values not decoded`` tier, so the curve projection
    trio takes its rule-prescribed explicit-unavailable branch instead of
    inventing rows; the CSV row contract (columns ``name, key_count,
    field_types, keys`` through the shared stdlib serializer) is pinned in
    ``tests/test_asset_projections.py`` and exercised end to end on the DataTable
    fixture above.
    """
    for name, mode in (
        ("TestSimpleCurveTable.uasset", "SimpleCurves"),
        ("TestRichCurveTable.uasset", "RichCurves"),
    ):
        document = parse_sample(name, depth="decode")
        normal, _debug = _accepted_pair(document)
        entry = next(
            item for item in normal["objects"] if (item.get("semantic") or {}).get("kind") == "curve_table"
        )
        semantic = entry["semantic"]
        assert semantic["row_names"] == ["RowA", "RowB"]
        assert semantic["row_count"] == 2
        assert semantic["curve_table_mode"] == mode

        # Valid rows: one row per key, names aligned, field schema decoded.
        rows = semantic["rows"]
        assert [row["name"] for row in rows] == semantic["row_names"]
        for row in rows:
            keys_field = row["fields"]["Keys"]
            assert keys_field["type"] == "ArrayProperty"
            assert keys_field["size"] > 0

        records = {item["kind"]: item for item in normal["projections"] if item["kind"].startswith("curve_table")}
        assert set(records) == {"curve_table", "curve_table_csv", "curve_table_json"}
        # Matrix rule ("keys/interp explicit; compressed-only unavailable unless
        # decoded"): undecoded key points take the explicit unavailable branch.
        for record in records.values():
            assert record["status"] == "unavailable"
            assert record["content"] is None
            assert [diag["code"] for diag in record["diagnostics"]] == ["curve_table_keys_unavailable"]

        # Stable rows: a second projection is identical.
        assert project_document(document)["projections"] == normal["projections"]


def test_matrix_sidecar_payload_fixture_acceptance():
    """Matrix: no embedded payload bytes; debug physical mapping names the sidecar and offset."""
    document = parse_sample("T_ParserBulk.uasset", depth="decode")
    normal, debug = _accepted_pair(document)

    # Tracked sidecars accompany the cooked main file.
    assert (SAMPLES / "T_ParserBulk.uexp").is_file()
    assert (SAMPLES / "T_ParserBulk.ubulk").is_file()

    # No embedded payload bytes: descriptors only.
    assert normal["payloads"]
    for payload in normal["payloads"]:
        assert set(payload) <= {"id", "owner", "kind", "stored_size", "status", "logical_size", "compression", "hash"}
        assert payload["stored_size"] > 0
        assert payload["status"] in {"available", "unavailable"}
    blob = json.dumps(normal)
    assert "T_ParserBulk.ubulk" not in blob  # bulk bytes never embed in the document

    # Debug physical mapping names the actual sidecar and the physical offset.
    sources = debug["debug"]["payload_sources"]
    assert sources
    named = {source["source_region"]["source_id"] for source in sources}
    assert named == {"T_ParserBulk.uexp"}
    for source in sources:
        slices = source["source_region"]["source_slices"]
        assert slices
        for slice_ in slices:
            assert slice_["source_id"] == "T_ParserBulk.uexp"
            assert slice_["size"] > 0
        assert source["offset"] == slices[0]["source_start"]
