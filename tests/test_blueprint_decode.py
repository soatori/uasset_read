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
    # E1 flip: projected graphs carry counts as plain ints (derived from nodes).
    assert ev["node_count"] == 14 == len(ev["nodes"])
    assert sum(len(n["pins"]) for n in ev["nodes"]) > 0
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
    # E1 flip: projected semantic always carries the key; the generated class
    # export owns no graph exports, so the list stays empty.
    assert not bpgc.semantic.get("graphs")
    assert bpgc.semantic["kind"] == "blueprint"


def test_combat_character_declaration_and_function_kinds():
    dec = _decode("BP_CombatCharacter.uasset", ("export:1",))
    bp = next(o for o in dec.objects if o.id == "export:1")
    assert bp.semantic is not None
    decl = bp.semantic["declaration"]
    assert decl["parent_class"] == "Character"
    # E1 flip: function declarations are their own top-level list of dicts.
    fns = {f["name"] for f in bp.semantic["function_declarations"]}
    assert "Aim" in fns
    assert "Move" in fns
    by_name = {g["name"]: g for g in bp.semantic["graphs"]}
    assert by_name["Aim"]["kind"] == "function"
    assert by_name["Move"]["kind"] == "function"


def test_combat_character_variables_names_and_guids():
    dec = _decode("BP_CombatCharacter.uasset", ("export:1",))
    bp = next(o for o in dec.objects if o.id == "export:1")
    assert bp.semantic is not None
    # E1 flip: variables -> variable_definitions (typed declaration records).
    names = [v["name"] for v in bp.semantic["variable_definitions"]]
    assert "Max HP" in names
    assert len(bp.semantic["variable_definitions"]) == 29
    for v in bp.semantic["variable_definitions"]:
        # VarType/reflection data lives on raw_type as the decoded
        # FEdGraphPinType fields plus the BPVariableDescription guid.
        raw = v["raw_type"]
        assert isinstance(raw, dict)
        vt = raw.get("VarType")
        assert isinstance(vt, dict)
        assert "pin_category" in vt
        guid = raw.get("VarGuid") or ""
        assert len(guid) == 32
        assert all(ch in "0123456789abcdef" for ch in guid)
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
    # E1 flip: component records are {name, class_name, object_id}.
    assert comps["Life Bar_GEN_VARIABLE"]["class_name"] == "WidgetComponent"
    assert comps["Camera_GEN_VARIABLE"]["class_name"] == "CameraComponent"
    assert all(c["object_id"] for c in bp.semantic["components"])


def test_combat_character_kismet_functions():
    # E1 flip: function dicts are project_function_analysis output —
    # function_name/bytecode_status/expression_count + instructions/CFG dicts.
    dec = _decode("BP_CombatCharacter.uasset", ("export:1",))
    bp = next(o for o in dec.objects if o.id == "export:1")
    assert bp.semantic is not None
    fns = bp.semantic.get("functions")
    assert fns is not None, "expected 'functions' key in semantic output"
    assert len(fns) > 0, "expected at least one decompiled function"
    for fn in fns:
        assert fn["function_name"], "function_name must be non-empty"
        assert fn["bytecode_status"] in {
            "parsed",
            "partial",
            "unavailable",
        }, f"unexpected bytecode_status: {fn['bytecode_status']}"
        assert "expression_count" in fn
        assert "cpp_code" not in fn
        assert "translation_status" not in fn
        if fn["bytecode_status"] == "parsed":
            assert fn["expression_count"] > 0, "parsed function must expose expressions"
            assert isinstance(fn["instructions"], list)
            assert all(isinstance(item, dict) and item.get("opcode") for item in fn["instructions"])
    # At least one function must be observable as parsed with instructions
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
        assert "instructions" not in fn, "asset depth must not embed full instruction IR"
        assert "cfg" not in fn, "asset depth must not embed full CFG"
        assert len(fn["expression_types"]) <= 128


def test_kismet_result_status_serializations():
    """KismetDecompiledResult must serialize parsed / partial / unavailable without cpp_code."""
    from uasset_read.kismet.result import KismetDecompiledResult
    from uasset_read.kismet.expressions import EX_True

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
        bytecode_status="unavailable",
        error_code="confirmed_no_script",
        script_metrics={"bytecode_buffer_size": 0},
    )
    d2 = no_script.to_dict()
    assert d2["bytecode_status"] == "unavailable"
    assert d2["bytecode_confidence"] == "unavailable"
    assert d2["error_code"] == "confirmed_no_script"
    assert d2["script_metrics"]["bytecode_buffer_size"] == 0

    failed = KismetDecompiledResult(
        function_name="H",
        signature="void H()",
        bytecode_status="unavailable",
        error_code="bytecode_decode_error",
        error_message="boom",
        fallback_reasons=["bytecode extraction error: boom"],
    )
    d3 = failed.to_dict()
    assert d3["bytecode_status"] == "unavailable"
    assert d3["error_message"] == "boom"
    assert d3["fallback_reasons"] == ["bytecode extraction error: boom"]

    partial = KismetDecompiledResult(
        function_name="P",
        signature="void P()",
        bytecode_status="partial",
    )
    assert partial.to_dict()["bytecode_confidence"] == "partial"

    with pytest.raises(ValueError, match="disallowed bytecode_status"):
        KismetDecompiledResult(function_name="I", signature="void I()", bytecode_status="unknown")


def _state_machines_from_semantic(semantic: dict) -> list[dict]:
    """Derive state-machine summaries from projected graphs (E1 flip).

    ``kind == "state_machine"`` survives the typed round trip; state_count
    comes from each state node's ``node_data.subgraph_references`` and
    node_count from the graph's node list — never the other way around.
    """
    machines: list[dict] = []
    for graph in semantic.get("graphs") or []:
        if graph.get("kind") != "state_machine":
            continue
        nodes = graph.get("nodes") or []
        if len(nodes) <= 1:
            continue
        state_count = sum(
            1 for n in nodes if (n.get("node_data") or {}).get("subgraph_references")
        )
        machines.append(
            {
                "name": graph.get("name"),
                "kind": "state_machine",
                "state_count": state_count,
                "node_count": graph.get("node_count", len(nodes)),
            }
        )
    return machines


def test_als_animbp_state_machines():
    """Verify ALS_AnimBP decode at export:274 contains state machines with at least one entry."""
    dec = _decode("ALS_AnimBP.uasset", ("export:274",))
    abp = next(o for o in dec.objects if o.id == "export:274")
    assert abp.semantic is not None
    assert abp.status.semantic == "complete", abp.status

    # E1 flip: state machines are derived from the projected graph kinds.
    state_machines = _state_machines_from_semantic(abp.semantic)
    assert state_machines, "expected at least one state machine"

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
        machines.extend(_state_machines_from_semantic(o.get("semantic") or {}))
    assert machines
    for sm in machines:
        assert sm["state_count"] <= sm["node_count"]
        if sm["node_count"] > 20:
            assert sm["state_count"] < sm["node_count"], sm


def _exec_pin_edges_from_graphs(graphs: list[dict], graph_name: str | None = None) -> list[dict]:
    """Collect unique undirected exec-pin edges from projected graph links.

    E1 flip: pin connectivity lives on projected ``pin["links"]`` records;
    the summary kind on ``exec_chains`` covers the bytecode CFG instead.
    Orientation mirrors ``summarize_exec_edges``: each undirected pair is
    emitted once, preferring the output→input direction when known.
    """
    # Direction lookup keyed by (node suffix, pin id).
    pin_direction: dict[tuple[str, str], str] = {}
    for graph in graphs:
        if graph_name is not None and graph.get("name") != graph_name:
            continue
        for node in graph.get("nodes") or []:
            node_key = str(node.get("id") or "").split("/")[-1]
            for pin in node.get("pins") or []:
                pid = pin.get("id")
                if pid:
                    pin_direction[(node_key, pid)] = pin.get("direction") or ""

    edges: list[dict] = []
    seen: set[frozenset[str]] = set()
    for graph in graphs:
        if graph_name is not None and graph.get("name") != graph_name:
            continue
        for node in graph.get("nodes") or []:
            from_node = str(node.get("id") or "").split("/")[-1]
            for pin in node.get("pins") or []:
                if (pin.get("category") or "") != "exec":
                    continue
                this_direction = pin.get("direction") or ""
                for link in pin.get("links") or []:
                    to_node = str(link.get("to_node_id") or "").split("/")[-1]
                    to_pin = link.get("to_pin_id")
                    from_pin = pin.get("id")
                    if not (from_pin and to_pin and from_node and to_node):
                        continue
                    if from_pin == to_pin and from_node == to_node:
                        continue
                    # Prefer output→input orientation. Locals only — rebind of
                    # the loop's from_node/from_pin would leak into the next
                    # pin of the same node and invent phantom edges.
                    edge_from_node, edge_to_node = from_node, to_node
                    edge_from_pin, edge_to_pin = from_pin, to_pin
                    if this_direction != "output":
                        if pin_direction.get((edge_to_node, edge_to_pin)) == "output":
                            edge_from_node, edge_to_node = edge_to_node, edge_from_node
                            edge_from_pin, edge_to_pin = edge_to_pin, edge_from_pin
                    pair = frozenset(
                        {(edge_from_node, edge_from_pin), (edge_to_node, edge_to_pin)}
                    )
                    if pair in seen:
                        continue
                    seen.add(pair)
                    edges.append(
                        {
                            "from_node": edge_from_node,
                            "from_pin": edge_from_pin,
                            "to_node": edge_to_node,
                            "to_pin": edge_to_pin,
                        }
                    )
    return edges


def test_exec_edges_available_for_event_graph():
    """exec_chains is the direct-edge CFG summary; pin edges stay on graphs."""
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        SAMPLES / "StackOBot_BP_Drone.uasset", depth="decode", tolerant=True
    )
    page = project_document(doc, depth="decode", max_bytes=2_000_000)
    summaries = []
    graphs = []
    for o in page.get("objects") or []:
        sem = o.get("semantic") or {}
        if sem.get("exec_chains"):
            summaries.append(sem["exec_chains"])
        graphs.extend(sem.get("graphs") or [])
    assert summaries, "projected blueprint semantic must carry exec_chains"
    for summary in summaries:
        assert summary["metadata"]["kind"] == "direct_exec_edge_summary"
        assert isinstance(summary["edges"], list)
    # Live fixture has 3 unique logical EventGraph exec connections.
    event_edges = _exec_pin_edges_from_graphs(graphs, "EventGraph")
    assert len(event_edges) == 3, event_edges
    for edge in event_edges:
        from_pin = edge["from_pin"]
        to_pin = edge["to_pin"]
        assert from_pin and to_pin and from_pin != to_pin, edge
        # Both ends must be pin GUIDs (32 hex), not display names.
        assert len(from_pin) == 32 and len(to_pin) == 32, edge


def test_node_name_is_not_graph_name_for_multi_node_graphs():
    """Nodes must not all be labeled with their owning graph name."""
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        SAMPLES / "StackOBot_BP_Drone.uasset", depth="decode", tolerant=True
    )
    page = project_document(doc, depth="decode", max_bytes=2_000_000)
    for o in page.get("objects") or []:
        for g in (o.get("semantic") or {}).get("graphs") or []:
            nodes = g.get("nodes") or []
            if len(nodes) <= 1:
                continue
            # E1 flip: projected node display name is "title".
            assert any(n.get("title") != g.get("name") for n in nodes)


def test_call_function_raw_properties_reach_node_data():
    """CallFunction nodes surface allow-listed tag-derived node_data."""
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        SAMPLES / "StackOBot_BP_Drone.uasset", depth="decode", tolerant=True
    )
    page = project_document(doc, depth="decode", max_bytes=2_000_000)
    nodes = [
        n
        for o in page.get("objects") or []
        for g in (o.get("semantic") or {}).get("graphs") or []
        for n in g.get("nodes") or []
        if "CallFunction" in (n.get("class_name") or "")
    ]
    assert nodes
    hits = [n for n in nodes if n.get("node_data")]
    assert hits, "CallFunction nodes must surface tag-derived node_data"
    # node_data stays within the allow-listed surface (no private bookkeeping).
    for n in hits:
        for key in n["node_data"]:
            assert not key.startswith("_"), key
            assert key in {
                "FunctionReference",
                "EventReference",
                "MemberName",
                "MemberParent",
                "VariableReference",
                "SelfContextInfo",
                "FunctionName",
                "CustomFunctionName",
                "subgraph_references",
                "bDefaultsToPure",
                "bDefaultsToPureFunc",
                "InputActionShortName",
                "OperationName",
                "TimelineName",
            }, key


def test_variable_nodes_do_not_fake_member_reference():
    """Variable nodes must not emit size/offset-only VariableReference stubs.

    Unmatched tags store ``{size, offset}`` only. Until MemberName/MemberParent
    (or equivalent primitives) survive in tags, that locator must not be
    projected as VariableReference. When MemberName *does* appear it must be a
    non-empty string primitive — a regression guard for the day fixtures carry
    real member tags, without inventing data today.
    """
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        SAMPLES / "BP_CombatCharacter.uasset",
        depth="decode",
        object_ids=["export:1"],
    )
    # Task 7 dual-offset instructions + CFG per function push the decode page
    # past the old 3 MB default; select the blueprint export like the sibling
    # K0-function gate and keep a measured budget that retains graph nodes.
    page = project_document(doc, depth="decode", max_bytes=5_000_000)
    nodes = [
        n
        for o in page.get("objects") or []
        for g in (o.get("semantic") or {}).get("graphs") or []
        for n in g.get("nodes") or []
        if "Variable" in (n.get("class_name") or "")
    ]
    assert nodes
    member_names = []
    for node in nodes:
        node_data = node.get("node_data") or {}
        var_ref = node_data.get("VariableReference")
        if var_ref is not None:
            assert isinstance(var_ref, dict)
            assert set(var_ref) - {"size", "offset"}, f"opaque locator leaked: {var_ref}"
        member = node_data.get("MemberName")
        if member is not None:
            assert isinstance(member, str) and member, f"MemberName must be a non-empty string: {member!r}"
            member_names.append(member)
    # Today's CombatCharacter Variable tags have no MemberName primitives.
    # If this assert fails after a fixture change, that is a visible inventory
    # flip — update the comment and keep the positive constraints above.
    assert member_names == []


def test_project_document_decode_max_bytes_keeps_k0_functions():
    """K3: decode + max_bytes still yields the function contract fields when the page fits."""
    from uasset_read.projection import project_document

    doc = parse_package_document(
        SAMPLES / "BP_CombatCharacter.uasset",
        depth="decode",
        object_ids=["export:1"],
    )
    # Budget large enough that the selected blueprint export is retained.
    # Task 7 adds dual-offset instructions + CFG per function (~4 MB page).
    projected = project_document(doc, depth="decode", max_bytes=5_000_000)
    assert projected.get("format") == "uasset_read.package"
    objs = projected.get("objects") or []
    assert objs, "budget must leave at least one object"
    bp = next((o for o in objs if o.get("id") == "export:1"), objs[0])
    fns = (bp.get("semantic") or {}).get("functions")
    assert fns, f"projected decode page must include functions; got semantic keys {list((bp.get('semantic') or {}).keys())}"
    for fn in fns:
        assert "expression_count" in fn
        assert "bytecode_status" in fn
        assert "cpp_code" not in fn
    assert any(f.get("expression_count", 0) > 0 for f in fns)


def test_kismet_one_failed_function_keeps_others():
    """K3: a failed function must not remove sibling results in the same owner list."""
    from uasset_read.kismet.result import KismetDecompiledResult

    # Simulate bridge output for one owner: one unavailable + one parsed sibling.
    failed = KismetDecompiledResult(
        function_name="Broken",
        signature="void Broken()",
        bytecode_status="unavailable",
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
    assert projected[0]["bytecode_status"] == "unavailable"
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

    # Compact decode of this sample is now multi-MB after Task 7 added
    # dual-offset instructions + CFG; 6 MB retains the full page.
    budget = 6_000_000
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
        assert "bytecode_status" in fn
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
    from tests.fixtures import open_sample_archive

    sample = SAMPLES / "BP_CombatCharacter.uasset"
    with open_sample_archive(sample) as (archive, summary, name_map, import_map, export_map):
        archive.set_property_version_gates(summary.file_version_ue4, summary.file_version_ue5)

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

    from uasset_read.kismet.bytecode_extractor import FUNCTION_EXPORT_CLASSES
    from uasset_read.serializers.object_resources import resolve_class_name

    function_exports = [
        e
        for e in export_map
        if resolve_class_name(e.class_index, import_map, export_map) in FUNCTION_EXPORT_CLASSES
    ]
    assert len(results) == len(function_exports) > 2
    by_status = {s: [r for r in results if r.bytecode_status == s] for s in ("parsed", "unavailable")}
    assert by_status["unavailable"], "injected failure must surface as an unavailable result"
    assert by_status["parsed"], "sibling Function exports must remain after one failure"
    failed = by_status["unavailable"][0]
    assert failed.error_code == "bytecode_decode_error"
    assert failed.error_message
    assert failed.fallback_reasons
    # At least one sibling still exposes a non-empty expression tree.
    assert any(r.expressions for r in by_status["parsed"])


def test_decode_pin_payload_key_set_is_frozen():
    """The emitted pin dict carries core identity + links, empty optionals omitted.

    Write-only UEdGraphPin fields must never leak. Task 6 intentionally retains
    defaults/subcategory/pass-through when present (plan: no read-and-discard);
    empty/null optionals are omitted so large AnimBlueprint pages stay in budget.
    """
    dec = _decode("StackOBot_BP_Drone.uasset", ("export:0",))
    bp = next(o for o in dec.objects if o.id == "export:0")
    graphs = bp.semantic["graphs"]
    pins = [p for g in graphs for n in g["nodes"] for p in n["pins"]]
    assert pins, "expected at least one decoded pin"
    core = {"id", "name", "direction", "category", "links"}
    retained = {
        "subcategory",
        "default_value",
        "default_object_ref",
        "default_text",
        "sub_pin_ids",
        "parent_pin_id",
        "reference_pass_through_pin_id",
        "is_const",
        "is_weak_pointer",
        "is_uobject_wrapper",
        "unknown_properties",
    }
    for pin in pins:
        assert core <= set(pin), sorted(pin)
        assert set(pin) <= core | retained, sorted(pin)


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
    assert counts["decode"] == counts["asset"] == 45, counts


# --------------------------------------------------------------------------- #
# Task 7: node addressability, partial failures, exec-edge orientation.
# --------------------------------------------------------------------------- #


def _low_level_graphs(sample: str):
    from tests.fixtures import open_sample_archive
    from uasset_read.serializers.blueprint_graph import read_blueprint_graphs

    with open_sample_archive(SAMPLES / sample) as (
        archive,
        summary,
        name_map,
        import_map,
        export_map,
    ):
        return read_blueprint_graphs(archive, summary, name_map, import_map, export_map)


def test_every_converted_node_id_is_addressable():
    """No converted node may have id=\"\"; fallback nodes stay export:N."""
    graphs = _low_level_graphs("StackOBot_BP_Drone.uasset")
    assert graphs
    for graph in graphs:
        for node in graph["nodes"]:
            assert node["id"].startswith("export:"), f"unaddressable node in {graph['id']}: {node}"
        for error in graph.get("parse_errors", []):
            assert error


def test_node_reader_failure_keeps_fallback_export_id(monkeypatch):
    """A controlled node-reader failure yields an addressable fallback node
    plus a surfaced graph parse error — never an empty id."""
    from uasset_read.exceptions import ParseError
    from tests.fixtures import open_sample_archive
    from uasset_read.serializers import graph_node

    sample = SAMPLES / "StackOBot_BP_Drone.uasset"
    with open_sample_archive(sample) as (archive, summary, name_map, import_map, export_map):
        real = graph_node.read_ue_graph_node
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ParseError("injected node failure")
            return real(*args, **kwargs)

        monkeypatch.setattr(graph_node, "read_ue_graph_node", flaky)
        from uasset_read.serializers.blueprint_graph import read_blueprint_graphs

        graphs = read_blueprint_graphs(archive, summary, name_map, import_map, export_map)

    assert calls["n"] >= 1
    all_nodes = [n for g in graphs for n in g["nodes"]]
    assert all_nodes
    for node in all_nodes:
        assert node["id"].startswith("export:"), node
    error_graphs = [g for g in graphs if g.get("parse_errors")]
    assert error_graphs, "the injected failure must surface in graph parse_errors"
    for g in error_graphs:
        for err in g["parse_errors"]:
            assert "injected node failure" in err or err


def test_exec_edges_are_oriented_unique_and_graph_local():
    """Every exec edge is output→input, graph-local, and undirected-unique.

    Keeps the StackOBot fixture count of three; this is a direct unique
    exec-edge summary, not a full runtime execution trace. E1 flip: pin edges
    are derived from projected pin links (exec category both ends); the
    bytecode-level summary lives on semantic["exec_chains"].
    """
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        SAMPLES / "StackOBot_BP_Drone.uasset", depth="decode", tolerant=True
    )
    page = project_document(doc, depth="decode", max_bytes=2_000_000)
    graphs = []
    for o in page.get("objects") or []:
        graphs.extend((o.get("semantic") or {}).get("graphs") or [])
    edges = _exec_pin_edges_from_graphs(graphs, "EventGraph")
    assert len(edges) == 3, edges

    # Direction/category metadata for endpoints, scoped to one decoded page.
    pin_meta: dict[str, tuple[str, str, str]] = {}
    graph_of_node: dict[str, str] = {}
    for g in graphs:
        for n in g.get("nodes") or []:
            graph_of_node[str(n.get("id") or "").split("/")[-1]] = g["id"]
            for p in n.get("pins") or []:
                pin_meta[p["id"]] = (n["id"], p.get("direction") or "", p.get("category") or "")

    seen_pairs: set[frozenset[str]] = set()
    for edge in edges:
        from_pin, to_pin = edge["from_pin"], edge["to_pin"]
        from_node, to_node = edge["from_node"], edge["to_node"]
        # Endpoints join the same emitted graph projection.
        assert graph_of_node.get(from_node) == graph_of_node.get(to_node), edge
        # Source is an output exec pin; target is an input exec pin.
        src = pin_meta.get(from_pin)
        dst = pin_meta.get(to_pin)
        assert src is not None and dst is not None, edge
        assert src[1] == "output" and src[2] == "exec", (edge, src)
        assert dst[1] == "input" and dst[2] == "exec", (edge, dst)
        pair = frozenset((from_pin, to_pin))
        assert pair not in seen_pairs, f"undirected duplicate: {edge}"
        seen_pairs.add(pair)


def test_stackobot_blueprint_semantic_is_projected_dict(stackobot_document):
    """E1: document-boundary blueprint semantic is a projected dict, not typed IR."""
    from tests.fixtures import find_blueprint_object

    obj = find_blueprint_object(stackobot_document)
    semantic = obj.semantic
    assert isinstance(semantic, dict)
    assert semantic["kind"] in {"blueprint", "anim_blueprint"}
    assert semantic["functions"], "functions[] must be projected dicts"
    assert isinstance(semantic["functions"][0], dict)
    assert "expression_count" in semantic["functions"][0]
    assert "control_flow" in semantic
