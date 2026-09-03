"""v2 blueprint graph extraction and conversion (issue #621 Phase 4.5).

Real-fixture tests: the graph binary readers are the shared serializers/graph*
machinery already proven on these samples by the v1 pipeline; this suite pins
the v2 conversion layer on top of it.
"""

from pathlib import Path


SAMPLES = Path(__file__).parent / "samples"


def _graphs_for(sample: str) -> list[dict]:
    """Open a fixture the way v2's decode pass does and return plain graph dicts."""
    from uasset_read.v2.source import FileSource
    from uasset_read.v2.package.legacy import _make_package_archive
    from uasset_read.serializers.package_summary import read_package_summary, read_name_table
    from uasset_read.serializers.object_resources import read_export_map, read_import_map
    from uasset_read.v2.blueprint_graph import read_blueprint_graphs

    src = FileSource(SAMPLES / sample)
    try:
        archive = _make_package_archive(src, tolerant=True)
        summary = read_package_summary(archive)
        name_map = read_name_table(archive, summary)
        archive.set_name_map(name_map)
        import_map = read_import_map(archive, summary, name_map)
        export_map = read_export_map(archive, summary, name_map)
        return read_blueprint_graphs(archive, summary, name_map, import_map, export_map)
    finally:
        src.close()


def test_stackobot_graphs_convert_with_pins_and_links():
    graphs = _graphs_for("StackOBot_BP_Drone.uasset")
    by_name = {g["name"]: g for g in graphs}
    assert set(by_name) == {"EventGraph", "UserConstructionScript"}
    ev = by_name["EventGraph"]
    assert ev["id"] == "export:4"
    assert ev["node_count"] == 14 == len(ev["nodes"])
    assert all(n["id"].startswith("export:") for n in ev["nodes"])
    # Pins must be decoded (this is what the v1 property stream alone cannot give).
    all_pins = [p for n in ev["nodes"] for p in n["pins"]]
    assert all_pins, "no pins decoded"
    assert all(p["id"] for p in all_pins)
    names = {p["name"] for p in all_pins}
    assert {"execute", "then"} <= names
    # Linked pins resolve to node ids inside the same package graph index.
    node_ids = {n["id"] for n in ev["nodes"]}
    for n in ev["nodes"]:
        for p in n["pins"]:
            for link in p["linked"]:
                assert link["to_node"] in node_ids, f"dangling link {link}"
    assert ev["pin_count"] == len(all_pins)
    assert ev["truncated"] == {"nodes": False, "pins": False}
    ucs = by_name["UserConstructionScript"]
    assert ucs["node_count"] == 1 == len(ucs["nodes"])
    assert ucs["truncated"]["nodes"] is False
