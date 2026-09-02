"""Blueprint v2 deep-decode contract (issue #621 Phase 4.5).

The decode branch previously attached a package-wide coarse node scan to every
Blueprint-family export. It now attaches real graphs (export-scoped, pin
decoded) to the export that owns them.
"""

from functools import lru_cache

from pathlib import Path

from uasset_read.v2.api import parse_package_document

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
        assert v["type"] == "opaque"
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
