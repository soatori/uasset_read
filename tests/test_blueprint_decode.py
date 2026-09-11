"""Blueprint v2 deep-decode contract (issue #621 Phase 4.5).

The decode branch previously attached a package-wide coarse node scan to every
Blueprint-family export. It now attaches real graphs (export-scoped, pin
decoded) to the export that owns them.
"""

from functools import lru_cache

from pathlib import Path

import pytest

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

    with pytest.raises(ValueError, match="disallowed bytecode_status"):
        KismetDecompiledResult(function_name="I", signature="void I()", bytecode_status="unknown")


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


def test_state_machine_state_count_not_node_count():
    """state_count comes from node_data.subgraph_references, never node_count."""
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        SAMPLES / "ALS_AnimBP.uasset",
        depth="decode",
        object_ids=["export:274"],
        tolerant=True,
    )
    page = project_document(doc, depth="decode", max_bytes=4_000_000)
    machines = []
    for o in page.get("objects") or []:
        machines.extend((o.get("semantic") or {}).get("state_machines") or [])
    assert machines
    for sm in machines:
        assert sm["state_count"] <= sm["node_count"]
        if sm["node_count"] > 20:
            assert sm["state_count"] < sm["node_count"], sm


def test_exec_edges_available_for_event_graph():
    """exec_chains surfaces exec-pin edges for the EventGraph."""
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        SAMPLES / "StackOBot_BP_Drone.uasset", depth="decode", tolerant=True
    )
    page = project_document(doc, depth="decode", max_bytes=2_000_000)
    chains = []
    for o in page.get("objects") or []:
        chains.extend((o.get("semantic") or {}).get("exec_chains") or [])
    assert chains and any(c.get("edges") for c in chains)


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


def test_cli_decode_max_bytes_keeps_k0_functions(tmp_path, monkeypatch):
    """K3: CLI --depth decode --max-bytes still yields K0 function fields.

    Joint regression for the public Blueprint JSON path (CLI), not just
    project_document: budget mode must keep expression summaries on the page.
    """
    import json
    import sys

    from uasset_read import cli

    # Compact decode of this sample is ~861 kB; 2 MB retains the full page.
    budget = 2_000_000
    sample = SAMPLES / "BP_CombatCharacter.uasset"
    out_path = tmp_path / "combat.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uasset_read",
            str(sample),
            "--depth",
            "decode",
            "--max-bytes",
            str(budget),
            "--output",
            str(out_path),
        ],
    )
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 0

    raw = out_path.read_text(encoding="utf-8")
    assert len(raw.encode("utf-8")) <= budget
    projected = json.loads(raw)
    assert projected.get("format") == "uasset_read.package"
    bp = next(o for o in projected.get("objects") or [] if o.get("id") == "export:1")
    fns = (bp.get("semantic") or {}).get("functions")
    assert fns, "CLI decode page must include semantic.functions"
    for fn in fns:
        assert "expression_count" in fn
        assert "expression_types" in fn
        assert "expressions_truncated" in fn
        assert "cpp_code" not in fn
    assert any(f.get("expression_count", 0) > 0 for f in fns)


def test_extract_bridge_one_failure_keeps_sibling_functions(monkeypatch):
    """K3: inject one decode failure among real Function exports; siblings stay.

    BP_CombatCharacter carries 45 Function/UFunction exports. Forcing the second
    parse_bytecode_stream call to fail must still return every export, with the
    failed one carrying structured error fields.
    """
    from uasset_read.exceptions import ParseError
    from uasset_read.kismet import bytecode_extractor
    from uasset_read.kismet.decompile_bridge import extract_kismet_decompiled
    from uasset_read.memory_safety import ResourceBudget
    from uasset_read.package import open_package_bundle
    from uasset_read.serializers.object_resources import read_export_map, read_import_map
    from uasset_read.serializers.package_summary import read_name_table, read_package_summary

    sample = SAMPLES / "BP_CombatCharacter.uasset"
    bundle = open_package_bundle(str(sample))
    archive = bundle.open_archive(tolerant=True)
    try:
        budget = ResourceBudget()
        summary = read_package_summary(archive, budget)
        archive.set_property_version_gates(summary.file_version_ue4, summary.file_version_ue5)
        name_map = read_name_table(archive, summary)
        archive.set_name_map(name_map)
        import_map = read_import_map(archive, summary, name_map)
        export_map = read_export_map(archive, summary, name_map)

        real_parse = bytecode_extractor.parse_bytecode_stream
        calls = {"n": 0}

        def flaky_parse(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise ParseError("injected K3 failure")
            return real_parse(*args, **kwargs)

        monkeypatch.setattr(bytecode_extractor, "parse_bytecode_stream", flaky_parse)
        results = extract_kismet_decompiled(
            archive,
            summary,
            name_map,
            import_map,
            export_map,
            tolerant=True,
        )
    finally:
        archive.close()

    from uasset_read.kismet.bytecode_extractor import FUNCTION_EXPORT_CLASSES
    from uasset_read.serializers.object_resources import resolve_class_name

    function_exports = [
        e
        for e in export_map
        if resolve_class_name(e.class_index, import_map, export_map) in FUNCTION_EXPORT_CLASSES
    ]
    assert len(results) == len(function_exports) > 2
    by_status = {s: [r for r in results if r.bytecode_status == s] for s in ("parsed", "failed")}
    assert by_status["failed"], "injected failure must surface as a failed result"
    assert by_status["parsed"], "sibling Function exports must remain after one failure"
    failed = by_status["failed"][0]
    assert failed.error_code == "bytecode_decode_error"
    assert failed.error_message
    assert failed.fallback_reasons
    # At least one sibling still exposes a non-empty expression tree.
    assert any(r.expressions for r in by_status["parsed"])


def test_decode_pin_payload_key_set_is_frozen():
    """The emitted pin dict carries exactly id/name/direction/category/linked.

    Write-only UEdGraphPin fields must never leak into this payload. The subtraction
    wave deletes those fields; this test is the contract that guards the emitter.
    """
    dec = _decode("StackOBot_BP_Drone.uasset", ("export:0",))
    bp = next(o for o in dec.objects if o.id == "export:0")
    graphs = bp.semantic["graphs"]
    pins = [p for g in graphs for n in g["nodes"] for p in n["pins"]]
    assert pins, "expected at least one decoded pin"
    for pin in pins:
        assert set(pin) == {"id", "name", "direction", "category", "linked"}, sorted(pin)


def test_generated_class_kismet_functions_survive_decode():
    """A BlueprintGeneratedClass owns Function exports (bytecode) but no FunctionGraph exports.

    decode is documented as a superset of asset (handlers_impl.py kismet projection;
    wiki Kismet.md depth monotonicity), so the graph gate must not drop its Kismet
    functions.
    """
    dec = _decode("BP_CombatCharacter.uasset", ("export:2",))
    bpgc = next(o for o in dec.objects if o.id == "export:2")
    fns = (bpgc.semantic or {}).get("functions")
    assert fns, "decode dropped the generated class's Kismet functions"


def test_generated_class_function_count_is_depth_independent():
    counts = {}
    for depth in ("asset", "decode"):
        doc = parse_package_document(
            SAMPLES / "BP_CombatCharacter.uasset", depth=depth, object_ids=["export:2"]
        )
        bpgc = next(o for o in doc.objects if o.id == "export:2")
        counts[depth] = len(((bpgc.semantic or {}).get("functions") or []))
    assert counts["decode"] == counts["asset"] == 42, counts
