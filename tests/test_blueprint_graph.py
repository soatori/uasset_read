"""v2 blueprint graph extraction and conversion (issue #621 Phase 4.5).

Real-fixture tests: the graph binary readers are the shared serializers/graph*
machinery already proven on these samples by the v1 pipeline; this suite pins
the v2 conversion layer on top of it.
"""

from pathlib import Path


SAMPLES = Path(__file__).parent / "samples"


def _graphs_for(sample: str) -> list[dict]:
    """Open a fixture the way v2's decode pass does and return plain graph dicts."""
    from uasset_read.package import open_package_bundle
    from uasset_read.serializers.package_summary import read_package_summary, read_name_table
    from uasset_read.serializers.object_resources import read_export_map, read_import_map
    from uasset_read.serializers.blueprint_graph import read_blueprint_graphs

    archive = open_package_bundle(str(SAMPLES / sample)).open_archive(tolerant=True)
    try:
        summary = read_package_summary(archive)
        name_map = read_name_table(archive, summary)
        archive.set_name_map(name_map)
        import_map = read_import_map(archive, summary, name_map)
        export_map = read_export_map(archive, summary, name_map)
        return read_blueprint_graphs(archive, summary, name_map, import_map, export_map)
    finally:
        archive.close()


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


# --------------------------------------------------------------------------- #
# Task 7: owning-node identity, owner-aware link resolution, partial decode.
# --------------------------------------------------------------------------- #


def test_read_pin_reference_preserves_owning_node():
    """FPinReference keeps the raw owning_node (FPackageIndex convention)."""
    import struct

    from uasset_read.archive import ByteArchive
    from uasset_read.serializers.graph_pin import read_pin_reference

    guid = bytes(range(16))
    blob = struct.pack("<ii", 0, 7) + guid  # b_null=0, owning_node=7, FGuid
    ref = read_pin_reference(ByteArchive(blob))
    assert ref is not None
    assert ref["owning_node"] == 7
    # Normalized to 32-char lowercase hex matching pin_id format.
    expected_guid = guid.hex()
    assert ref["pin_guid"] == expected_guid

    # Null reference consumes only the marker and stays None.
    assert read_pin_reference(ByteArchive(struct.pack("<i", -1))) is None


def test_resolve_pin_links_prefers_owner_over_duplicate_guid():
    """Duplicate pin GUIDs resolve by (owning_node, pin_guid), not last-write."""
    from uasset_read.serializers.blueprint_graph import resolve_pin_links

    def _node(node_id, pin_id):
        return {
            "id": node_id,
            "pins": [
                {"id": pin_id, "name": "then", "direction": "output", "category": "exec", "linked": []}
            ],
        }

    shared = "a" * 32
    graphs = [
        {
            "id": "export:0",
            "nodes": [_node("export:1", shared), _node("export:2", shared)],
            "_pin_links": [
                # Owner says the target is export:1 (owning_node 2 = 1-based
                # export index) even though export:2 also carries the same
                # GUID (and would win a last-write scan).
                {"from_node": 2, "from_pin": shared, "to_pin": shared, "to_owning_node": 2},
            ],
        }
    ]
    resolve_pin_links(graphs)
    g = graphs[0]
    assert g["edge_count"] == 1
    assert g["unresolved_links"] == 0
    src_pin = g["nodes"][0]["pins"][0]
    assert src_pin["linked"] == [{"to_node": "export:1", "to_pin": shared}]


def test_resolve_pin_links_duplicate_guid_without_owner_is_unresolved():
    """No owner + duplicate GUID candidates is ambiguous — never arbitrarily picked."""
    from uasset_read.serializers.blueprint_graph import resolve_pin_links

    shared = "b" * 32

    def _node(node_id):
        return {
            "id": node_id,
            "pins": [{"id": shared, "name": "execute", "direction": "input", "category": "exec", "linked": []}],
        }

    graphs = [
        {
            "id": "export:0",
            "nodes": [_node("export:1"), _node("export:2")],
            "_pin_links": [
                {"from_node": 2, "from_pin": shared, "to_pin": shared, "to_owning_node": None},
            ],
        }
    ]
    resolve_pin_links(graphs)
    g = graphs[0]
    assert g["edge_count"] == 0
    assert g["unresolved_links"] == 1
    assert g["nodes"][0]["pins"][0]["linked"] == []


def test_resolve_pin_links_guid_fallback_single_candidate():
    """Owner unavailable + exactly one GUID candidate still resolves."""
    from uasset_read.serializers.blueprint_graph import resolve_pin_links

    guid = "c" * 32
    graphs = [
        {
            "id": "export:0",
            "nodes": [
                {
                    "id": "export:1",
                    "pins": [{"id": "d" * 32, "name": "then", "direction": "output", "category": "exec", "linked": []}],
                },
                {
                    "id": "export:2",
                    "pins": [{"id": guid, "name": "execute", "direction": "input", "category": "exec", "linked": []}],
                },
            ],
            "_pin_links": [
                {"from_node": 2, "from_pin": "d" * 32, "to_pin": guid, "to_owning_node": 0},
            ],
        }
    ]
    resolve_pin_links(graphs)
    g = graphs[0]
    assert g["edge_count"] == 1
    assert g["nodes"][0]["pins"][0]["linked"] == [{"to_node": "export:2", "to_pin": guid}]


def _raw_graph_links(sample: str) -> list[dict]:
    """Independently re-read every node export and collect raw pin-link records.

    Expected targets in owner-aware regressions are derived from the fixture's
    serialized owning_node + pin GUID values via read_pin_reference — never
    from the current resolve_pin_links output.
    """
    from uasset_read.package import open_package_bundle
    from uasset_read.serializers.package_summary import read_package_summary, read_name_table
    from uasset_read.serializers.object_resources import read_export_map, read_import_map, resolve_class_name
    from uasset_read.serializers.graph_node import read_ue_graph_node

    archive = open_package_bundle(str(SAMPLES / sample)).open_archive(tolerant=True)
    try:
        summary = read_package_summary(archive)
        name_map = read_name_table(archive, summary)
        archive.set_name_map(name_map)
        import_map = read_import_map(archive, summary, name_map)
        export_map = read_export_map(archive, summary, name_map)
        records: list[dict] = []
        for exp_idx, exp in enumerate(export_map):
            cls = resolve_class_name(exp.class_index, import_map, export_map) or ""
            if "Node" not in cls:
                continue
            try:
                node = read_ue_graph_node(archive, name_map, summary, export_map, import_map, exp)
            except Exception:
                continue
            for pin in node.pins:
                for entry in pin.linked_to_raw:
                    records.append(
                        {
                            "src_export_1b": exp_idx + 1,
                            "src_pin_id": str(pin.pin_id),
                            "src_pin_name": str(pin.pin_name),
                            "src_category": str(pin.pin_type.pin_category) if pin.pin_type else "",
                            "target_owning_node": entry.get("owning_node"),
                            "target_pin_guid": str(entry.get("pin_guid", "")),
                        }
                    )
        return records
    finally:
        archive.close()


def test_stackobot_owner_aware_link_targets():
    """StackOBot raw links resolve to the fixture's serialized owning node.

    Probe-pinned case: export:12 pin 'X' links to a GUID that appears on both
    export:23 and export:24; the serialized owning_node selects export:23.
    A GUID-only last-write resolver would pick export:24.
    """
    graphs = _graphs_for("StackOBot_BP_Drone.uasset")
    raw = _raw_graph_links("StackOBot_BP_Drone.uasset")
    assert raw, "fixture must expose raw pin links"

    # Map resolved linked entries per (source node, source pin id).
    resolved: dict[tuple[str, str], set[str]] = {}
    for g in graphs:
        for n in g["nodes"]:
            for p in n["pins"]:
                for link in p["linked"]:
                    resolved.setdefault((n["id"], p["id"]), set()).add(link["to_node"])

    checked = 0
    for rec in raw:
        owner = rec["target_owning_node"]
        if not isinstance(owner, int) or owner <= 0:
            continue
        expected = f"export:{owner - 1}"
        key = (f"export:{rec['src_export_1b'] - 1}", rec["src_pin_id"])
        if key not in resolved:
            continue
        assert expected in resolved[key], f"{rec}: expected owner target {expected}, got {resolved[key]}"
        checked += 1
    assert checked >= 20, f"expected the fixture's links to be owner-resolvable, checked {checked}"

    # Pin the known duplicate-GUID disambiguation case.
    pinned = [
        r
        for r in raw
        if r["src_export_1b"] == 13
        and r["src_pin_name"] == "X"
        and r["target_owning_node"] == 24
        and r["target_pin_guid"].startswith("cd10eacf")
    ]
    assert pinned, "expected the export:12 'X' -> export:23 duplicate-GUID link"
    key = ("export:12", pinned[0]["src_pin_id"])
    assert "export:23" in resolved[key]
    assert "export:24" not in resolved[key], "last-write duplicate must not win"


def test_combat_character_owner_aware_exec_link():
    """BP_CombatCharacter exec link that GUID-only resolution misidentifies.

    Probe-pinned case: export:177 pin 'execute' (exec) links to GUID
    597d059e... whose owning_node is export:415. The GUID also appears on
    export:426, which a package-wide last-write index would select.
    """
    graphs = _graphs_for("BP_CombatCharacter.uasset")
    raw = _raw_graph_links("BP_CombatCharacter.uasset")

    resolved: dict[tuple[str, str], set[str]] = {}
    for g in graphs:
        for n in g["nodes"]:
            for p in n["pins"]:
                for link in p["linked"]:
                    resolved.setdefault((n["id"], p["id"]), set()).add(link["to_node"])

    exec_links = [r for r in raw if r["src_category"] == "exec" and isinstance(r["target_owning_node"], int) and r["target_owning_node"] > 0]
    assert exec_links, "fixture must expose exec raw links with owners"

    # Every owner-resolvable exec link must land on its serialized owner.
    for rec in exec_links:
        expected = f"export:{rec['target_owning_node'] - 1}"
        key = (f"export:{rec['src_export_1b'] - 1}", rec["src_pin_id"])
        if key not in resolved:
            continue
        assert expected in resolved[key], f"{rec}: expected {expected}, got {resolved[key]}"

    pinned = [
        r
        for r in exec_links
        if r["src_export_1b"] == 178
        and r["src_pin_name"] == "execute"
        and r["target_owning_node"] == 416
        and r["target_pin_guid"].startswith("597d059e")
    ]
    assert pinned, "expected the export:177 execute -> export:415 exec link"
    key = ("export:177", pinned[0]["src_pin_id"])
    assert "export:415" in resolved[key], resolved[key]
    # The guid-only last-write candidate (export:426) must never appear.
    assert "export:426" not in resolved[key], resolved[key]


def _stub_export(outer_1based: int, name: str = "E"):
    from types import SimpleNamespace

    return SimpleNamespace(
        object_name=name,
        outer_index=SimpleNamespace(index=outer_1based),
        class_index=None,
    )


def _stub_object(table_index: int, class_name: str, obj_id: str):
    from types import SimpleNamespace

    return SimpleNamespace(table_index=table_index, class_name=class_name, id=obj_id)


def test_resolve_graph_owner_nine_hop_chain():
    """A nine-hop outer chain resolves to the terminal Blueprint owner."""
    from uasset_read.parsers.legacy_reader import _resolve_graph_owner

    # export:0 = Blueprint; export:1..8 chain down to the graph at export:8.
    export_map = [_stub_export(0, "BP")]
    for i in range(1, 9):
        export_map.append(_stub_export(i, f" Intermediate{i}"))
    objects = [_stub_object(0, "Blueprint", "export:0")]
    objects += [_stub_object(i, "EdGraph" if i == 8 else "SomeObject", f"export:{i}") for i in range(1, 9)]
    # Graph at export:8 -> outer export:7 -> ... -> export:0 (Blueprint).
    assert _resolve_graph_owner(8, export_map, objects) == "export:0"


def test_resolve_graph_owner_cyclic_chain_terminates():
    """A cyclic outer chain terminates within the bound and stays unresolved."""
    from uasset_read.parsers.legacy_reader import _resolve_graph_owner

    # export:0 outer -> export:1, export:1 outer -> export:0 (cycle), no family class.
    export_map = [_stub_export(2, "A"), _stub_export(1, "B")]
    objects = [_stub_object(0, "SomeObject", "export:0"), _stub_object(1, "SomeObject", "export:1")]
    assert _resolve_graph_owner(0, export_map, objects) is None


def test_ftext_history_as_number_value_and_cursor():
    """FText history type 4 (AsNumber) decodes value and leaves the cursor
    on the next Pin field, per FTextHistory_FormatNumber::Serialize."""
    import struct
    from types import SimpleNamespace

    from uasset_read.archive import ByteArchive
    from uasset_read.serializers.graph_helpers import _read_ftext_value

    # Flags + HistoryType=AsNumber(4) + SourceValue(Int=42) + no format
    # options + empty CultureName, then a sentinel "next Pin field".
    blob = b"".join(
        [
            struct.pack("<i", 0),  # Flags
            struct.pack("<b", 4),  # HistoryType = AsNumber
            struct.pack("<b", 0),  # FFormatArgumentType::Int
            struct.pack("<i", 42),  # IntValue
            struct.pack("<i", 0),  # bHasFormatOptions = false (FArchive bool)
            struct.pack("<i", 0),  # CultureName = empty FString
            struct.pack("<i", 0x12345678),  # sentinel: next pin field
        ]
    )
    # FEditorObjectVersion >= AddedAlwaysSignNumberFormattingOption (21):
    # with options present the AlwaysSign bool would be gated in; this fixture
    # proves the no-options path plus exact cursor placement.
    summary = SimpleNamespace(
        package_flags=0,
        custom_versions=[SimpleNamespace(guid="ed68b0e4e94294f40bda31a241bb462e", version=40)],
    )
    archive = ByteArchive(blob)
    value, flags, history_type, consumed = _read_ftext_value(archive, tolerant=True, summary=summary)
    assert flags == 0
    assert history_type == 4
    assert value == "42"
    assert archive.tell() == len(blob) - 4, "cursor must sit exactly after the FText field"
    assert archive.read_i32() == 0x12345678, "subsequent Pin fields stay aligned"


def test_ftext_history_as_number_format_options_with_always_sign():
    """Format-options branch includes the FEditorObjectVersion-gated AlwaysSign bool."""
    import struct
    from types import SimpleNamespace

    from uasset_read.archive import ByteArchive
    from uasset_read.serializers.graph_helpers import _read_ftext_value

    blob = b"".join(
        [
            struct.pack("<i", 0),
            struct.pack("<b", 4),
            struct.pack("<b", 1),  # UInt
            struct.pack("<I", 7),
            struct.pack("<i", 1),  # bHasFormatOptions = true
            struct.pack("<i", 0),  # AlwaysSign (FEditorObjectVersion >= 21)
            struct.pack("<i", 1),  # UseGrouping
            struct.pack("<b", 0),  # RoundingMode
            struct.pack("<i", 1),  # MinimumIntegralDigits
            struct.pack("<i", 6),  # MaximumIntegralDigits
            struct.pack("<i", 0),  # MinimumFractionalDigits
            struct.pack("<i", 3),  # MaximumFractionalDigits
            struct.pack("<i", 0),  # CultureName empty
            struct.pack("<i", 0x55AA55AA),
        ]
    )
    summary = SimpleNamespace(
        package_flags=0,
        custom_versions=[SimpleNamespace(guid="ed68b0e4e94294f40bda31a241bb462e", version=40)],
    )
    archive = ByteArchive(blob)
    value, _flags, history_type, _ = _read_ftext_value(archive, tolerant=True, summary=summary)
    assert history_type == 4 and value == "7"
    assert archive.tell() == len(blob) - 4
    assert archive.read_i32() == 0x55AA55AA


def test_ftext_unsupported_history_stops_at_field_boundary():
    """An unsupported history type raises at the field boundary — no guessed skip."""
    import struct

    import pytest

    from uasset_read.archive import ByteArchive
    from uasset_read.exceptions import ParseError
    from uasset_read.serializers.graph_helpers import _read_ftext_value

    blob = struct.pack("<i", 0) + struct.pack("<b", 9) + b"\x00" * 32
    archive = ByteArchive(blob)
    with pytest.raises(ParseError, match="history_type"):
        _read_ftext_value(archive, tolerant=True)
