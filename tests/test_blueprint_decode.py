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
    assert bpgc.status.semantic == "partial"
    assert "graphs" not in bpgc.semantic
    assert bpgc.semantic["kind"] == "blueprint"
