"""Blueprint v2 deep-decode contract (issue #621 Phase 4.5).

The decode branch previously attached a package-wide coarse node scan to every
Blueprint-family export. It now attaches real graphs (export-scoped, pin
decoded) to the export that owns them.
"""

from functools import lru_cache

from pathlib import Path

from uasset_read.package import parse_package_document

SAMPLES = Path(__file__).parent / "samples"


@lru_cache(maxsize=None)
def _decode(sample: str, object_ids: tuple[str, ...]):
    return parse_package_document(SAMPLES / sample, depth="decode", object_ids=list(object_ids))


def test_stackobot_blueprint_asset_export_gets_real_graphs():
    dec = _decode("StackOBot_BP_Drone.uasset", ("export:0",))
    bp = next(o for o in dec.objects if o.id == "export:0")
    assert bp.semantic is not None
    assert bp.status.semantic == "complete", bp.status
    graphs = {g["name"]: g for g in bp.semantic["graphs"]}
    assert set(graphs) == {"EventGraph", "UserConstructionScript"}
    ev = graphs["EventGraph"]
    assert ev["node_count"] == 14 == len(ev["nodes"])
    assert ev["pin_count"] > 0
    # graph kind derivation
    assert ev["kind"] == "event_graph"
    assert graphs["UserConstructionScript"]["kind"] == "construction_script"
    # old coarse package-wide scan key is gone
    assert "graph" not in bp.semantic
    # no spurious diagnostics
    assert not [d for d in dec.diagnostics if d.code == "BLUEPRINT_EXTERNAL_PIN_LINK"]


def test_stackobot_generated_class_export_stays_summary_partial():
    dec = _decode("StackOBot_BP_Drone.uasset", ("export:1",))
    bpgc = next(o for o in dec.objects if o.id == "export:1")
    assert bpgc.semantic is not None
    assert bpgc.status.semantic == "partial"
    assert "graphs" not in bpgc.semantic
    assert bpgc.semantic["kind"] == "blueprint"


def test_combat_character_declaration_and_function_kinds():
    dec = _decode("BP_CombatCharacter.uasset", ("export:1",))
    bp = next(o for o in dec.objects if o.id == "export:1")
    assert bp.semantic is not None
    decl = bp.semantic["declaration"]
    assert decl["parent_class"] == "Character"
    fns = {f["name"]: f["id"] for f in decl["functions"]}
    assert "Aim" in fns
    assert "Move" in fns
    by_name = {g["name"]: g for g in bp.semantic["graphs"]}
    assert by_name["Aim"]["kind"] == "function"
    assert by_name["Move"]["kind"] == "function"


def test_combat_character_variables_names_and_guids():
    dec = _decode("BP_CombatCharacter.uasset", ("export:1",))
    bp = next(o for o in dec.objects if o.id == "export:1")
    assert bp.semantic is not None
    names = [v["name"] for v in bp.semantic["variables"]]
    assert "Max HP" in names
    assert len(bp.semantic["variables"]) == 29
    for v in bp.semantic["variables"]:
        # VarType is now decoded as FEdGraphPinType
        assert isinstance(v["type"], dict)
        assert "pin_category" in v["type"]
        assert len(v["guid"]) == 32
        assert all(ch in "0123456789abcdef" for ch in v["guid"])
    feature_names = [c.feature for c in bp.coverage]
    assert "blueprint.variables" in feature_names


def test_combat_character_components_tree():
    # Full-package decode: SCS_Node properties are parsed only when the parse
    # set covers their exports (object_ids narrowing would skip them).
    dec = parse_package_document(SAMPLES / "BP_CombatCharacter.uasset", depth="decode")
    bp = next(o for o in dec.objects if o.id == "export:1")
    assert bp.semantic is not None
    comps = {c["name"]: c for c in bp.semantic["components"]}
    assert "Life Bar_GEN_VARIABLE" in comps
    assert comps["Life Bar_GEN_VARIABLE"]["type"] == "WidgetComponent"
    assert comps["Camera_GEN_VARIABLE"]["type"] == "CameraComponent"
    # one of the components nests under another (ChildNodes linkage)
    parents = [c["parent"] for c in bp.semantic["components"] if c["parent"] is not None]
    assert parents, "expected at least one child component"
    ids = {c["id"] for c in bp.semantic["components"]}
    assert all(p in ids for p in parents)


def test_combat_character_kismet_functions():
    # K0: function_name/signature/bytecode_status + expression summary/tree
    dec = _decode("BP_CombatCharacter.uasset", ("export:1",))
    bp = next(o for o in dec.objects if o.id == "export:1")
    assert bp.semantic is not None
    fns = bp.semantic.get("functions")
    assert fns is not None, "expected 'functions' key in semantic output"
    assert len(fns) > 0, "expected at least one decompiled function"
    for fn in fns:
        assert fn["function_name"], "function_name must be non-empty"
        assert fn["signature"], "signature must be non-empty"
        assert fn["bytecode_status"] in {
            "parsed",
            "no_script",
            "failed",
            "unknown",
        }, f"unexpected bytecode_status: {fn['bytecode_status']}"
        assert "expression_count" in fn
        assert "expression_types" in fn
        assert "expressions_truncated" in fn
        assert "cpp_code" not in fn
        assert "translation_status" not in fn
        if fn["bytecode_status"] == "parsed":
            assert fn["expression_count"] > 0, "parsed function must expose expressions"
            assert len(fn["expression_types"]) == min(fn["expression_count"], 128)
            assert "expressions" in fn, "depth=decode must include expression tree"
            assert isinstance(fn["expressions"], list)
            assert all(isinstance(e, dict) and "Inst" in e for e in fn["expressions"])
    # At least one function must be observable as parsed with expressions
    assert any(f["bytecode_status"] == "parsed" and f.get("expression_count", 0) > 0 for f in fns)
    feature_names = [c.feature for c in bp.coverage]
    assert "blueprint.kismet" in feature_names
    kismet_cov = next(c for c in bp.coverage if c.feature == "blueprint.kismet")
    assert kismet_cov.status in ("present", "partial")


def test_combat_character_kismet_asset_depth_summary():
    """depth=asset projects expression_count/types without the full tree."""
    from uasset_read import parse_package_document

    doc = parse_package_document(
        "tests/samples/BP_CombatCharacter.uasset",
        depth="asset",
        object_ids=["export:1"],
    )
    bp = next(o for o in doc.objects if o.id == "export:1")
    fns = (bp.semantic or {}).get("functions")
    assert fns, "asset depth should still project kismet function summaries"
    for fn in fns:
        assert "expression_count" in fn
        assert "expression_types" in fn
        assert "expressions_truncated" in fn
        assert "expressions" not in fn, "asset depth must not embed the full tree"
        assert len(fn["expression_types"]) <= 128


def test_kismet_result_status_serializations():
    """KismetDecompiledResult must serialize parsed / no_script / failed without cpp_code."""
    from uasset_read.kismet.result import KismetDecompiledResult
    from uasset_read.kismet.expressions.literals import EX_True

    true_expr = EX_True()
    true_expr.StatementIndex = 0
    parsed = KismetDecompiledResult(
        function_name="F",
        signature="void F()",
        expressions=[true_expr],
        bytecode_status="parsed",
    )
    d = parsed.to_dict()
    assert d["bytecode_status"] == "parsed"
    assert d["bytecode_confidence"] == "verified"
    assert d["expressions"][0]["Inst"] == "EX_True"
    assert "cpp_code" not in d
    assert "translation_status" not in d

    no_script = KismetDecompiledResult(
        function_name="G",
        signature="void G()",
        bytecode_status="no_script",
        error_code="confirmed_no_script",
        script_metrics={"bytecode_buffer_size": 0},
    )
    d2 = no_script.to_dict()
    assert d2["bytecode_status"] == "no_script"
    assert d2["bytecode_confidence"] == "no_script"
    assert d2["error_code"] == "confirmed_no_script"
    assert d2["script_metrics"]["bytecode_buffer_size"] == 0

    failed = KismetDecompiledResult(
        function_name="H",
        signature="void H()",
        bytecode_status="failed",
        error_code="bytecode_decode_error",
        error_message="boom",
        fallback_reasons=["bytecode extraction error: boom"],
    )
    d3 = failed.to_dict()
    assert d3["bytecode_status"] == "failed"
    assert d3["error_message"] == "boom"
    assert d3["fallback_reasons"] == ["bytecode extraction error: boom"]


def test_als_animbp_state_machines():
    """Verify ALS_AnimBP decode at export:274 contains state_machines with at least one entry."""
    dec = _decode("ALS_AnimBP.uasset", ("export:274",))
    abp = next(o for o in dec.objects if o.id == "export:274")
    assert abp.semantic is not None
    assert abp.status.semantic == "complete", abp.status

    # Verify state_machines exists and has at least one entry
    state_machines = abp.semantic.get("state_machines")
    assert state_machines is not None, "expected 'state_machines' key in semantic output"
    assert len(state_machines) > 0, "expected at least one state machine"

    # Verify each state machine has the required fields
    for sm in state_machines:
        assert "name" in sm, "state machine must have 'name' field"
        assert "kind" in sm, "state machine must have 'kind' field"
        assert "state_count" in sm, "state machine must have 'state_count' field"
        assert "node_count" in sm, "state machine must have 'node_count' field"
        assert sm["kind"] == "state_machine", f"expected kind='state_machine', got '{sm['kind']}'"
        assert sm["state_count"] > 0, "state_count must be positive"
        assert sm["node_count"] > 0, "node_count must be positive"

    # Verify specific state machines exist (based on ALS_AnimBP structure)
    sm_names = {sm["name"] for sm in state_machines}
    assert "Overlay States" in sm_names, "expected 'Overlay States' state machine"
    assert "Main Movement States" in sm_names, "expected 'Main Movement States' state machine"
    assert "Jump States" in sm_names, "expected 'Jump States' state machine"

    # Coverage entry
    feature_names = [c.feature for c in abp.coverage]
    assert "anim_blueprint.state_machines" in feature_names
    sm_cov = next(c for c in abp.coverage if c.feature == "anim_blueprint.state_machines")
    assert sm_cov.status == "present"
    assert len(state_machines) == 17, f"expected 17 state machines, got {len(state_machines)}"


def test_project_document_decode_max_bytes_keeps_k0_functions():
    """K3: decode + max_bytes still yields K0 function fields when the page fits."""
    from uasset_read.projection import project_document

    doc = parse_package_document(
        SAMPLES / "BP_CombatCharacter.uasset",
        depth="decode",
        object_ids=["export:1"],
    )
    # Budget large enough that the selected blueprint export is retained.
    projected = project_document(doc, depth="decode", max_bytes=500_000)
    assert projected.get("format") == "uasset_read.package"
    objs = projected.get("objects") or []
    assert objs, "budget must leave at least one object"
    bp = next((o for o in objs if o.get("id") == "export:1"), objs[0])
    fns = (bp.get("semantic") or {}).get("functions")
    assert fns, f"projected decode page must include functions; got semantic keys {list((bp.get('semantic') or {}).keys())}"
    for fn in fns:
        assert "expression_count" in fn
        assert "expression_types" in fn
        assert "expressions_truncated" in fn
        assert "cpp_code" not in fn
    assert any(f.get("expression_count", 0) > 0 for f in fns)


def test_kismet_one_failed_function_keeps_others():
    """K3: a failed function must not remove sibling results in the same owner list."""
    from uasset_read.kismet.result import KismetDecompiledResult

    # Simulate bridge output for one owner: one failed + one parsed sibling.
    failed = KismetDecompiledResult(
        function_name="Broken",
        signature="void Broken()",
        bytecode_status="failed",
        error_code="bytecode_decode_error",
        error_message="boom",
        fallback_reasons=["bytecode extraction error: boom"],
    ).to_dict()
    parsed = KismetDecompiledResult(
        function_name="Fine",
        signature="void Fine()",
        bytecode_status="parsed",
        expressions=[],
    ).to_dict()
    # Handler projection must keep both entries (no filtering by status).
    from uasset_read.parsers.asset_types.handlers_impl import _project_kismet_functions

    projected = _project_kismet_functions([failed, parsed], include_expressions=True)
    assert [p["function_name"] for p in projected] == ["Broken", "Fine"]
    assert projected[0]["bytecode_status"] == "failed"
    assert projected[0]["error_code"] == "bytecode_decode_error"
    assert projected[1]["bytecode_status"] == "parsed"
