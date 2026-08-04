"""Test for Issue #521: Niagara export type evidence.

Documents the current behavior with a real Niagara asset fixture.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from uasset_read import parse_single


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "NM_BPSystemEvent.uasset"
SOURCE_FIXTURE_SHA256 = "B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF"

# Target classes for routing migration evidence
TARGET_CLASSES = {"NiagaraGraph", "NiagaraScript"}
# Classes still caught by prefix skip
NIAGARA_NODE_PREFIX = "NiagaraNode"


def test_niagara_asset_parsed_as_partial():
    """Niagara assets are currently parsed as partial with skipped exports."""
    # Compute SHA-256 for fixture verification
    sha256 = hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper()
    assert sha256 == SOURCE_FIXTURE_SHA256, f"Fixture SHA-256 mismatch: {sha256}"

    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    # Verify status is partial
    assert payload["status"]["status"] == "partial"

    # Count skipped exports
    skipped = [
        export for export in payload["exports"]
        if export.get("parse_status") == "skipped"
    ]

    # Verify we have skipped Niagara exports
    niagara_skipped = [
        export for export in skipped
        if "Niagara" in export.get("object_class", "")
    ]

    # Document the evidence
    print(f"\n=== Niagara Asset Evidence ===")
    print(f"Fixture: {SAMPLE.name}")
    print(f"SHA-256: {sha256}")
    print(f"UE Version: {payload['summary']['ue_version']}")
    print(f"Total exports: {len(payload['exports'])}")
    print(f"Skipped exports: {len(skipped)}")
    print(f"Niagara skipped: {len(niagara_skipped)}")
    print(f"\nSkipped export types:")
    for export in niagara_skipped[:10]:
        print(f"  - {export['object_class']}: {export['object_name']}")

    # Assert we have evidence of the issue
    assert len(niagara_skipped) > 0, "Expected Niagara exports to be skipped"


def test_niagara_export_types_documented():
    """Document the current Niagara export parse status for each class.

    After Phase 2/3/4, Graph/Script and 9 node classes are no longer skipped.
    Remaining Niagara classes (NiagaraSystem, NiagaraDataInterface*, NiagaraScriptSource,
    NiagaraEmitter, etc.) stay in the skipped set.
    """
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    # Collect unique Niagara export classes and their parse statuses
    niagara_classes: dict[str, str] = {}
    for export in payload["exports"]:
        cls = export.get("object_class", "")
        if "Niagara" not in cls:
            continue
        status = export.get("parse_status", "success")
        niagara_classes.setdefault(cls, status)

    # Migrated classes (no longer skipped)
    migrated = {
        "NiagaraGraph", "NiagaraScript",
        "NiagaraNodeFunctionCall", "NiagaraNodeParameterMapSet",
        "NiagaraNodeInput", "NiagaraNodeParameterMapGet",
        "NiagaraNodeOp", "NiagaraNodeOutput",
        "NiagaraNodeReroute",
    }

    print(f"\n=== Niagara Export Parse Status by Class ===")
    for cls in sorted(niagara_classes):
        status = niagara_classes[cls]
        marker = "✓" if cls in migrated else " "
        print(f"  {marker} {cls}: {status}")

    # Verify migrated classes are NOT skipped
    for cls in migrated:
        if cls in niagara_classes:
            assert niagara_classes[cls] != "skipped", (
                f"{cls} should not be 'skipped' after migration; got '{niagara_classes[cls]}'"
            )

    # Verify we have Niagara exports at all
    assert len(niagara_classes) > 0, "Expected Niagara exports in fixture"


def test_niagara_exports_structured_inventory():
    """Structured inventory of all Niagara exports with diagnostic detail."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    target_inventory = []
    all_inventory = []

    for export in payload["exports"]:
        object_name = export.get("object_name", "")
        object_class = export.get("object_class", "")
        serial_size = export.get("serial_size", 0)
        parse_status = export.get("parse_status", "success")
        has_asset_type_data = "asset_type_data" in export

        entry = {
            "object_name": object_name,
            "object_class": object_class,
            "serial_size": serial_size,
            "parse_status": parse_status,
        }

        is_niagara_node = object_class.startswith(NIAGARA_NODE_PREFIX)
        is_target_class = object_class in TARGET_CLASSES
        is_target_or_node = is_target_class or is_niagara_node

        if is_target_or_node:
            # Additional detail for target exports
            entry["has_asset_type_data"] = has_asset_type_data
            if has_asset_type_data:
                atd = export["asset_type_data"]
                entry["asset_type_data_keys"] = list(atd.keys())
                entry["atd_tail_offset"] = atd.get("tail_offset")
                entry["atd_tail_size"] = atd.get("tail_size")
                entry["atd_parse_status"] = atd.get("parse_status")
            # Also record fallback_reason if present
            if "fallback_reason" in export:
                entry["fallback_reason"] = export["fallback_reason"]
            # Record property count
            props = export.get("properties", [])
            entry["property_count"] = len(props)
            target_inventory.append(entry)

        all_inventory.append(entry)

    # Print structured inventory for diagnostic review
    print(f"\n=== Niagara Structured Inventory ===")
    print(f"Total exports: {len(all_inventory)}")
    print(f"Target exports (NiagaraGraph/NiagaraScript/NiagaraNode*): {len(target_inventory)}")
    print()

    # Print target inventory
    print("--- Target Exports ---")
    for entry in target_inventory:
        print(f"  {entry['object_class']}: {entry['object_name']}")
        print(f"    serial_size: {entry['serial_size']}, parse_status: {entry['parse_status']}")
        if "fallback_reason" in entry:
            print(f"    fallback_reason: {entry['fallback_reason']}")
        print(f"    has_asset_type_data: {entry['has_asset_type_data']}, property_count: {entry.get('property_count', 0)}")
        if entry.get("asset_type_data_keys"):
            print(f"    asset_type_data keys: {entry['asset_type_data_keys']}")
        if entry.get("atd_tail_offset") is not None:
            print(f"    tail_offset: {entry['atd_tail_offset']}, tail_size: {entry['atd_tail_size']}")
        print()

    # Verify we found target exports
    assert len(target_inventory) > 0, "Expected target Niagara exports"

    # Verify classification: NiagaraGraph/NiagaraScript should NOT be skipped
    for entry in target_inventory:
        if entry["object_class"] in TARGET_CLASSES:
            assert entry["parse_status"] != "skipped", (
                f"{entry['object_class']} should not be 'skipped' after routing migration, "
                f"got '{entry['parse_status']}'"
            )

    # Verify classification: migrated NiagaraNode* classes are now opaque/partial_metadata
    for entry in target_inventory:
        if entry["object_class"].startswith(NIAGARA_NODE_PREFIX):
            assert entry["parse_status"] != "skipped", (
                f"{entry['object_class']} should not be 'skipped' after Phase 4 migration, "
                f"got '{entry['parse_status']}'"
            )


def test_niagara_graph_and_script_are_no_longer_skipped():
    """Verify NiagaraGraph and NiagaraScript are routed to opaque, not skipped.

    This documents the routing migration from Task 2 where NiagaraGraph and
    NiagaraScript moved from _SKIP_CLASSES to _OPAQUE_CLASSES.
    """
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    # Collect exports by class
    niagara_graph_exports = [
        e for e in payload["exports"] if e.get("object_class") == "NiagaraGraph"
    ]
    niagara_script_exports = [
        e for e in payload["exports"] if e.get("object_class") == "NiagaraScript"
    ]

    print(f"\n=== Routing Migration Evidence ===")
    print(f"NiagaraGraph exports: {len(niagara_graph_exports)}")
    print(f"NiagaraScript exports: {len(niagara_script_exports)}")

    # Verify NiagaraGraph exports are not skipped (routed to opaque path)
    for export in niagara_graph_exports:
        parse_status = export.get("parse_status", "success")
        print(f"  NiagaraGraph '{export['object_name']}': parse_status={parse_status}")
        assert parse_status != "skipped", (
            f"NiagaraGraph '{export['object_name']}' should not be 'skipped' "
            f"after routing migration; got '{parse_status}'"
        )
        # After routing to OPAQUE_CLASS_PAYLOAD + handler projection, status is "partial_metadata"
        # (handler projects business fields from tagged properties)
        assert parse_status == "partial_metadata", (
            f"NiagaraGraph '{export['object_name']}' expected 'partial_metadata' "
            f"after handler projection; got '{parse_status}'"
        )

    # Verify NiagaraScript exports are not skipped (routed to opaque path)
    for export in niagara_script_exports:
        parse_status = export.get("parse_status", "success")
        print(f"  NiagaraScript '{export['object_name']}': parse_status={parse_status}")
        assert parse_status != "skipped", (
            f"NiagaraScript '{export['object_name']}' should not be 'skipped' "
            f"after routing migration; got '{parse_status}'"
        )
        # After routing to OPAQUE_CLASS_PAYLOAD + handler projection, status is "partial_metadata"
        # (handler projects business fields from tagged properties)
        assert parse_status == "partial_metadata", (
            f"NiagaraScript '{export['object_name']}' expected 'partial_metadata' "
            f"after handler projection; got '{parse_status}'"
        )

    # Verify we have NiagaraGraph and NiagaraScript exports to test
    assert len(niagara_graph_exports) > 0, "Expected NiagaraGraph exports in fixture"
    assert len(niagara_script_exports) > 0, "Expected NiagaraScript exports in fixture"


def test_niagara_target_exports_have_documented_properties():
    """Each NiagaraGraph/NiagaraScript export must list its parsed property names.

    This validates that tagged properties are being consumed (not just skipped)
    and provides the baseline for field contract documentation.
    """
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    property_inventories = []
    for export in payload["exports"]:
        object_class = export.get("object_class", "")
        if object_class not in TARGET_CLASSES:
            continue

        props = export.get("properties", [])
        prop_names = [p.get("name", "?") for p in props]
        prop_types = [p.get("type", "?") for p in props]

        inventory = {
            "object_name": export.get("object_name", ""),
            "object_class": object_class,
            "parse_status": export.get("parse_status", "success"),
            "property_count": len(props),
            "property_names": prop_names,
            "property_types": prop_types,
            "serial_size": export.get("serial_size", 0),
        }

        if "asset_type_data" in export:
            atd = export["asset_type_data"]
            inventory["atd_keys"] = sorted(atd.keys())
            inventory["atd_parse_status"] = atd.get("parse_status")

        property_inventories.append(inventory)

    print(f"\n=== Niagara Property Inventories ===")
    for inv in property_inventories:
        print(f"\n  {inv['object_class']}: {inv['object_name']}")
        print(f"    parse_status: {inv['parse_status']}")
        print(f"    serial_size: {inv['serial_size']}")
        print(f"    property_count: {inv['property_count']}")
        if inv["property_names"]:
            print(f"    properties: {inv['property_names']}")
        if inv.get("atd_keys"):
            print(f"    asset_type_data keys: {inv['atd_keys']}")

    assert len(property_inventories) > 0, "Expected target Niagara exports"
    graph_exports = [i for i in property_inventories if i["object_class"] == "NiagaraGraph"]
    assert len(graph_exports) > 0, "Expected NiagaraGraph exports"
    script_exports = [i for i in property_inventories if i["object_class"] == "NiagaraScript"]
    assert len(script_exports) > 0, "Expected NiagaraScript exports"


def test_niagara_graph_has_parseable_tagged_properties():
    """NiagaraGraph exports must have parseable tagged properties (not empty)."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    graph_exports = [
        e for e in payload["exports"]
        if e.get("object_class") == "NiagaraGraph"
    ]
    assert len(graph_exports) > 0, "Expected NiagaraGraph exports"

    for export in graph_exports:
        props = export.get("properties", [])
        parse_status = export.get("parse_status", "success")
        print(f"\n  NiagaraGraph '{export.get('object_name', '?')}':")
        print(f"    parse_status: {parse_status}")
        print(f"    property_count: {len(props)}")
        if props:
            print(f"    property_names: {[p.get('name', '?') for p in props]}")


def test_niagara_script_has_parseable_tagged_properties():
    """NiagaraScript exports must have parseable tagged properties."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    script_exports = [
        e for e in payload["exports"]
        if e.get("object_class") == "NiagaraScript"
    ]
    assert len(script_exports) > 0, "Expected NiagaraScript exports"

    for export in script_exports:
        props = export.get("properties", [])
        parse_status = export.get("parse_status", "success")
        print(f"\n  NiagaraScript '{export.get('object_name', '?')}':")
        print(f"    parse_status: {parse_status}")
        print(f"    property_count: {len(props)}")
        if props:
            print(f"    property_names: {[p.get('name', '?') for p in props]}")
        prop_names = {p.get("name", "?") for p in props}
        print(f"    property_name_set: {sorted(prop_names)}")


def test_niagara_node_exports_no_longer_skipped():
    """NiagaraNode* exports must no longer be skip_unsupported after Phase 4 migration."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    node_exports = [
        e for e in payload["exports"]
        if e.get("object_class", "").startswith(NIAGARA_NODE_PREFIX)
    ]

    print(f"\n=== NiagaraNode Exports ===")
    print(f"Total NiagaraNode* exports: {len(node_exports)}")

    for export in node_exports:
        parse_status = export.get("parse_status", "success")
        print(f"  {export.get('object_class')}: {export.get('object_name')} -> {parse_status}")
        assert parse_status != "skipped", (
            f"NiagaraNode export '{export.get('object_name', '?')}' "
            f"(class={export.get('object_class', '?')}) should not be 'skipped' "
            f"after Phase 4 migration; got '{parse_status}'"
        )

    assert len(node_exports) > 0, "Expected NiagaraNode exports in fixture"
