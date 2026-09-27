# tests/test_projection_v3.py
"""v3 projection consistency: JSON/CLI/Agent share one PackageDocument path."""

import copy


from tests.fixtures import find_blueprint_object, parse_sample
from uasset_read.projection import project_document
from uasset_read.projections.cpp_render import render_cpp


def test_json_and_cpp_use_the_same_document():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    json_view = project_document(document, view="semantic")
    blueprint = find_blueprint_object(document)
    assert isinstance(blueprint.semantic, dict)
    cpp_view = render_cpp(blueprint.semantic, mode="declaration")
    assert json_view["package"]["name"]
    assert cpp_view.header_text
    assert json_view["format_version"] == "3.0"


def test_large_payloads_are_not_embedded_by_default(document):
    output = project_document(document, view="semantic")
    assert output.get("payloads", []) == []


def test_projection_embeds_type_aware_content(document):
    output = project_document(document, view="semantic")
    assert "projections" in output
    assert output["projections"], "registry projections must be embedded, not left empty"
    assert all("source_object_id" in item for item in output["projections"])
    assert all(item["embedded"] for item in output["projections"])


def test_canonical_file_api_is_not_paginated(stackobot_document, tmp_path):
    from uasset_read.projections.bundle import build_canonical_document, write_projected_document

    full = build_canonical_document(stackobot_document)
    expected_ids = {obj.id for obj in stackobot_document.objects}
    assert expected_ids <= {item["id"] for item in full["objects"]}
    path = write_projected_document(stackobot_document, tmp_path / "full.json")
    assert path.exists()


def test_project_cpp_loads_object_semantic_dict(stackobot_document):
    from uasset_read.projection import project_cpp

    blueprint = find_blueprint_object(stackobot_document)
    result = project_cpp(stackobot_document, object_id=blueprint.id, mode="declaration")
    assert result.header_text
    assert result.translation_stats["declarations"] > 0


def test_build_projection_records_filters_object_and_kind(stackobot_document):
    from uasset_read.projection import build_projection_records

    blueprint = find_blueprint_object(stackobot_document)
    records = build_projection_records(
        stackobot_document,
        object_ids=[blueprint.id],
        kinds=["cpp_declaration"],
    )
    assert records
    assert all(item.source_object_id == blueprint.id for item in records)
    assert all(item.kind == "cpp_declaration" for item in records)


def test_bounded_projection_scopes_records_to_page(document):

    page = project_document(document, view="semantic", limit=3)
    page_ids = {item["id"] for item in page["objects"]}
    record_ids = {item["source_object_id"] for item in page["projections"]}
    assert record_ids <= page_ids
    # Unlimited response covers more objects than the bounded page.
    full = project_document(document, view="semantic")
    assert len(full["projections"]) >= len(page["projections"])


def test_paginated_cli_and_agent_share_projection_layer(document):
    """Bounded responses still carry type-aware records after pagination."""
    page = project_document(document, view="semantic", limit=5)
    assert "projections" in page
    assert all(item["embedded"] for item in page["projections"])


def test_canonical_document_uses_sole_creator_projection_api(stackobot_document):
    """CLI -o / batch materialize projections only via build_projection_records."""
    from uasset_read.projection import build_projection_records
    from uasset_read.projections.bundle import build_canonical_document
    from uasset_read.projections.records import projection_to_dict

    canonical = build_canonical_document(stackobot_document)
    expected = [projection_to_dict(item) for item in build_projection_records(stackobot_document)]
    assert canonical["projections"] == expected


def test_agent_get_object_exposes_projection_records():
    """get_object always carries projections[] (records or explicit empty)."""
    from tests.fixtures import find_blueprint_object, parse_sample, sample_path
    from uasset_read.agent_tools import get_object

    document = parse_sample("StackOBot_BP_Drone.uasset", depth="asset")
    path = str(sample_path("StackOBot_BP_Drone.uasset"))
    blueprint = find_blueprint_object(document)
    fetched = get_object(path, blueprint.id)
    assert fetched["id"] == blueprint.id
    assert "projections" in fetched
    assert fetched["projections"]
    assert all(item["source_object_id"] == blueprint.id for item in fetched["projections"])
    assert all(item["embedded"] for item in fetched["projections"])

    # Families with no type-aware projector still get an explicit empty list.
    plain = next(obj for obj in document.objects if obj.class_name == "Function")
    empty = get_object(path, plain.id)
    assert empty["id"] == plain.id
    assert empty["projections"] == []


def test_canonical_payload_uses_physical_sidecar_slice():
    """Canonical payload descriptors must not expose virtual offsets as main-file offsets."""
    from uasset_read.projections.bundle import build_canonical_document

    document = parse_sample("T_ParserBulk.uasset", depth="asset")
    export = next(obj for obj in document.objects if obj.id == "export:0")
    assert export.serial_region is not None
    assert export.serial_region.source_slices

    payload = next(
        item for item in build_canonical_document(document)["payloads"] if item["owner"] == export.id
    )
    physical = export.serial_region.source_slices[0]
    assert physical.source_id.endswith(".uexp")
    assert payload["source_region"] == "uexp"
    assert payload["offset"] == physical.source_start
    assert payload["stored_size"] == physical.size


def test_budget_truncation_actual_matches_final_serialized_response(stackobot_document):
    from uasset_read.projection import json_byte_size

    result = project_document(stackobot_document, depth="decode", max_bytes=500_000)
    assert result["objects"]
    assert result["truncation"]["actual"] == json_byte_size(result)
    assert json_byte_size(result) <= 500_000


# --- _enforce_budget on a hand-built envelope (no parse, no PackageDocument) ---


def _budget_envelope(pad: int = 500) -> dict:
    """20 same-width objects with every list the trim must re-scope."""
    ids = [f"export:{i:02d}" for i in range(20)]
    relations = [{"kind": "outer_of", "from": oid, "to": f"export:{(i + 1) % 20:02d}"} for i, oid in enumerate(ids)]
    relations += [
        {"kind": "class_of", "from": ids[0], "to": "import:0", "target_path": "Engine.Object"},
        {"kind": "class_of", "from": ids[19], "to": "import:1", "target_path": "Engine.Actor"},
    ]
    return {
        "format": "uasset_read.package",
        "format_version": "3.0",
        "objects": [{"id": oid, "name": oid.replace(":", "_"), "pad": "x" * pad} for oid in ids],
        "relations": relations,
        "dependencies": [
            {"index": 0, "class": "Class", "object_name": "Object", "package_name": "Engine"},
            {"index": 1, "class": "Class", "object_name": "Actor", "package_name": "Engine"},
        ],
        "projections": [{"source_object_id": oid, "kind": "cpp_declaration", "embedded": True} for oid in ids],
        "diagnostics": [
            {"severity": "warning", "code": "PKG_NOTE", "message": "package-level", "stage": "package.summary"},
            {
                "severity": "warning",
                "code": "OBJ_NOTE",
                "message": "first",
                "stage": "objects.export",
                "object_id": ids[0],
            },
            {
                "severity": "warning",
                "code": "OBJ_NOTE",
                "message": "last",
                "stage": "objects.export",
                "object_id": ids[19],
            },
        ],
        "summary": {"object_count": 20, "asset_object_ids": ids, "total_imports": 2, "total_exports": 20},
    }


def test_enforce_budget_keeps_the_longest_fitting_prefix():
    from uasset_read.projection import _enforce_budget, json_byte_size

    env = _budget_envelope()
    full = json_byte_size(env)
    all_objects = list(env["objects"])
    unit = json_byte_size({"objects": env["objects"][:2]}) - json_byte_size({"objects": env["objects"][:1]})
    budget = full - 2 * unit  # room for the TRUNCATED + truncation overhead, then some

    result = _enforce_budget(env, budget, offset=0, page_total=20)
    kept = len(result["objects"])
    assert 0 < kept < 20, f"expected a partial page, kept {kept}"
    assert json_byte_size(result) <= budget
    assert result["next_offset"] == kept
    assert result["truncation"]["objects_dropped"] == 20 - kept
    # Maximality: one more object would have blown the budget.
    bigger = copy.deepcopy(result)
    bigger["objects"].append(all_objects[kept])
    bigger["next_offset"] = kept + 1
    assert json_byte_size(bigger) > budget


def test_enforce_budget_rescopes_every_object_owned_list():
    from uasset_read.projection import _enforce_budget, json_byte_size

    env = _budget_envelope()
    budget = json_byte_size(env) - 2 * 500
    result = _enforce_budget(env, budget, offset=0, page_total=20)
    kept = {o["id"] for o in result["objects"]}
    assert 0 < len(kept) < 20

    assert all(r["from"] in kept for r in result["relations"])
    # One hop only: imports reachable solely from a dropped object go too.
    targets = {r["to"] for r in result["relations"]}
    assert all(f"import:{d['index']}" in targets for d in result["dependencies"])
    assert {p["source_object_id"] for p in result["projections"]} <= kept
    kept_diags = [d for d in result["diagnostics"] if d["code"] == "OBJ_NOTE"]
    assert kept_diags and all(d["object_id"] in kept for d in kept_diags)
    assert any(d["code"] == "PKG_NOTE" for d in result["diagnostics"]), "package-level diagnostics survive"
    assert any(d["code"] == "TRUNCATED" for d in result["diagnostics"])


def test_enforce_budget_all_dropped_yields_no_cursor():
    from uasset_read.projection import _enforce_budget

    # Objects dominate the envelope: the budget holds the fixed overhead but
    # not a single object, so nothing survives and no cursor may be handed out.
    budget = 5000
    result = _enforce_budget(_budget_envelope(pad=5000), budget, offset=0, page_total=20)
    assert result["objects"] == []
    assert "next_offset" not in result, "a cursor that advances nothing ends nothing"
    assert result["truncation"]["objects_dropped"] == 20
    assert any(d["code"] == "BUDGET_EXHAUSTED" for d in result["diagnostics"])


def test_enforce_budget_actual_is_the_final_compact_byte_count():
    from uasset_read.projection import _enforce_budget, json_byte_size

    env = _budget_envelope()
    budget = json_byte_size(env) - 2 * 500
    result = _enforce_budget(env, budget, offset=0, page_total=20)
    assert result["truncation"]["reason"] == "max_bytes"
    assert result["truncation"]["budget"] == budget
    assert result["truncation"]["actual"] == json_byte_size(result) <= budget


def test_enforce_budget_returns_a_fitting_envelope_untouched():
    from uasset_read.projection import _enforce_budget, json_byte_size

    env = _budget_envelope()
    generous = json_byte_size(env) + 10_000
    result = _enforce_budget(env, generous, offset=0, page_total=20)
    assert result is env
    assert "truncation" not in result
    assert not any(d["code"] == "TRUNCATED" for d in result["diagnostics"])
