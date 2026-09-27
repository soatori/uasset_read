"""Sample quality gates for the v3 package-first projection path (Task R5).

Acceptance numbers are locked to the plan/spec/manifest table. Sample-facing
checks consume projected E1 dicts (not live IR dataclasses) except where
``BlueprintCorrelation`` itself is the named semantic trace API.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from tests.fixtures import (
    find_blueprint_object,
    find_function,
    find_material_graph,
    parse_sample,
)
from uasset_read.parsers.blueprint.correlation import BlueprintCorrelation
from uasset_read.package import parse_package_document

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(__file__).parent / "samples"
SCHEMA = json.loads(
    (ROOT / "docs" / "designs" / "contract" / "package_document_v3.schema.json").read_text(encoding="utf-8")
)
USMAP = SAMPLES / "UnversionedTest.usmap"
CONTAINERS = SAMPLES / "containers"

COMPLETENESS_ENUM = {"complete", "partial", "opaque", "unavailable", "failed"}
STATUS_ENUM = {"translated", "represented", "untranslated", "unavailable"}


def test_completeness_label_mapping_contract():
    """v3 completeness enum: never overclaim complete; opaque/failed when warranted."""
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
        (("cpp_declaration", "text/x-c++hdr"),),
        code="blueprint_render_failed",
        message="render failed",
        stage="projection.blueprint",
    )
    assert projection_to_dict(failed_records[0])["completeness"] == "failed"
    assert projection_to_dict(failed_records[0])["status"] == "unavailable"


def count_kismet_expressions(semantic_dict) -> int:
    """Sum expression_count over projected function dicts on one semantic."""
    total = 0
    for fn in (semantic_dict.get("functions") or []):
        total += fn.get("expression_count") or 0
    return total


def _function_dicts(document) -> list[dict]:
    out: list[dict] = []
    for obj in document.objects:
        for fn in ((obj.semantic or {}).get("functions") or []):
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
        list(class_props.values())
        if isinstance(class_props, dict)
        else [entry.value for entry in class_props.entries]
    )
    assert any(
        isinstance(v, dict) and v.get("kind") == "opaque" for v in class_values
    ), "unmapped class export must stay bounded opaque"


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
        depth="package",
    )
    assert result.document is None
    assert result.status == "unavailable"
    assert result.reason in {"chunk_bytes_unavailable", "zen_package_fixture_unavailable"}
    assert result.diagnostics
    # Real Zen package parsing stays deferred until redistributable fixtures exist.
    assert all(
        d.stage.startswith("zen") or d.stage.startswith("container") for d in result.diagnostics
    )


# --------------------------------------------------------------------------- #
# Gate 6 — C++ projection: oracle AST + dual-offset migration traces
# --------------------------------------------------------------------------- #


def test_cpp_projection_dual_offset_traces():
    from uasset_read.projections.cpp_render import render_cpp

    # Migration dual-offset trace for every top-level instruction (StackOBot 85).
    stackobot = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    stackobot_semantic = find_blueprint_object(stackobot).semantic
    assert isinstance(stackobot_semantic, dict)
    migration = render_cpp(stackobot_semantic, mode="migration")
    stats = migration.translation_stats
    assert stats["instructions_seen"] == 85
    assert stats["instructions_seen"] == (
        stats["translated"] + stats["represented"] + stats["untranslated"] + stats["unavailable"]
    )
    traces = [
        line
        for line in migration.source_text.splitlines()
        if line.strip().startswith("// stmt=")
    ]
    assert len(traces) == stats["instructions_seen"]
    for line in traces:
        # Dual-offset envelope: logical statement_index + serialized range.
        assert "stmt=" in line
        assert "serialized=[" in line
        assert "status=" in line


# --------------------------------------------------------------------------- #
# Gate 7 — type-aware projections on recognized families
# --------------------------------------------------------------------------- #


def test_type_aware_projection_acceptance():
    from uasset_read.projections.registry import CAPABILITY_MATRIX, ProjectorRegistry

    registry = ProjectorRegistry.default()

    material_doc = parse_sample("StackOBot_M_BotBase.uasset", depth="decode")
    projections = registry.project_document(material_doc)
    material = next(obj for obj in material_doc.objects if obj.id == "export:0")
    assert len((material.semantic or {}).get("material_graph", {}).get("expressions", [])) == 39
    builder = [item for item in projections if item.kind == "material_editor_builder"]
    assert builder and builder[0].status in {"represented", "unavailable"}
    assert all(item.source_object_id for item in projections)
    assert all(item.status in STATUS_ENUM for item in projections)

    # Cooked material: explicit unavailable, never a complete fake builder.
    cooked = parse_sample("TestMaterial.uasset", depth="decode")
    cooked_builder = [
        item for item in registry.project_document(cooked) if item.kind == "material_editor_builder"
    ]
    assert cooked_builder
    assert cooked_builder[0].status == "unavailable"

    # Blueprint family: specialized C++ projections embedded.
    bp_doc = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    bp_projections = registry.project_document(bp_doc)
    bp_kinds = {item.kind for item in bp_projections}
    assert "cpp_declaration" in bp_kinds
    assert "cpp_migration" in bp_kinds

    # Data assets use CSV/JSON where decoded.
    table = parse_sample("FirstPerson_DT_WeaponList.uasset", depth="asset")
    table_kinds = {item.kind for item in registry.project_document(table)}
    assert {"data_table", "data_table_csv", "data_table_json"} <= table_kinds

    # Capability matrix still declares the recognized families.
    families = {entry["family"] for entry in CAPABILITY_MATRIX}
    assert {"blueprint_family", "material", "data_table", "curve_table"} <= families


# --------------------------------------------------------------------------- #
# Gate 8 — single-document output + contract schema
# --------------------------------------------------------------------------- #


def test_single_document_contains_all_projection_sections(stackobot_document):
    from uasset_read.projections.bundle import build_canonical_document

    output = build_canonical_document(stackobot_document)
    assert output["format_version"] == "3.0"
    assert output["package"]
    assert output["objects"]
    assert "projections" in output
    assert output["projections"], "canonical document must embed type-aware projections"
    assert all(item["embedded"] for item in output["projections"])
    assert all(item["completeness"] in COMPLETENESS_ENUM for item in output["projections"])
    assert all(item["status"] in STATUS_ENUM for item in output["projections"])
    assert all("provenance" in item for item in output["projections"])
    # Ordinary asset/graph boundaries do not split the document.
    assert len(output["objects"]) == len(stackobot_document.objects)
    assert {item["id"] for item in output["objects"]} == {
        obj.id for obj in stackobot_document.objects
    }

    # Canonical envelope must satisfy the committed v3 contract schema.
    jsonschema.validate(output, SCHEMA)


def test_bounded_project_document_pages_are_schema_valid(stackobot_document):
    from uasset_read.projection import project_document

    for view in ("semantic", "raw", "debug"):
        page = project_document(stackobot_document, depth="object", view=view, limit=3)
        json.loads(json.dumps(page, ensure_ascii=False))
        jsonschema.validate(page, SCHEMA)
        assert page["format_version"] == "3.0"
        assert all(item["embedded"] for item in page["projections"])
        assert all(item["completeness"] in COMPLETENESS_ENUM for item in page["projections"])


# --------------------------------------------------------------------------- #
# Gate 9 — byte accounting
# --------------------------------------------------------------------------- #


def test_canonical_byte_accounting_scopes_are_contract_shaped(stackobot_document):
    from uasset_read.projections.bundle import build_canonical_document

    output = build_canonical_document(stackobot_document)
    scopes = output["byte_accounting"]
    assert isinstance(scopes, list)
    assert scopes
    for scope in scopes:
        assert scope["object_id"].startswith("export:")
        assert scope["window"]["size"] >= 0
        assert scope["leaves"]
        for leaf in scope["leaves"]:
            assert leaf["size"] > 0
            assert leaf["status"] in {"decoded", "opaque", "payload", "unavailable"}
