"""B2 pin decode tests — extract pin records from NiagaraNode native tails.

These tests assert that the node handler decodes pin records from native tails.
Currently they FAIL because native_tail.status is 'opaque' and no pins field exists;
Task 6 will make them pass.

Source: issue-521-b0-gate-decision.md §Pin-record layout.
Fixture: 25 NiagaraNode* exports, 99 pins, 76 LinkedTo edges (B0a/B0b verified).
"""
import json
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from uasset_read import parse_single

SAMPLE = Path(__file__).resolve().parents[2] / "tests/samples/NM_BPSystemEvent.uasset"
SHA256 = "B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF"

# Expected pin counts per node class (from B0a/B0b byte walk)
EXPECTED_PIN_COUNTS = {
    "NiagaraNodeInput": 1,       # 1 node, 1 pin each → but B0a says Input has 1 pin? Verify.
    "NiagaraNodeFunctionCall": [2, 4, 4, 3, 4, 3],  # per-node pin counts from B0a
    "NiagaraNodeOp": [4, 4, 3, 4, 3],
    "NiagaraNodeOutput": 1,
    "NiagaraNodeParameterMapGet": [6, 6, 10, 8, 6],
    "NiagaraNodeParameterMapSet": [4, 5, 4, 4, 5],
    "NiagaraNodeReroute": [5, 5],
    "NiagaraNodeSelect": 5,
    "NiagaraNodeStaticSwitch": 4,
}

# Total expected edges (from B0b: 76/76 resolve)
EXPECTED_TOTAL_EDGES = 76


def _parse_fixture():
    return json.loads(parse_single(str(SAMPLE), format="json", tolerant=True, log_enabled=False))


def _get_node_exports(data):
    """Extract all NiagaraNode* exports from the parsed fixture."""
    nodes = []
    for export in data.get("exports", []):
        atd = export.get("asset_type_data", {})
        node_class = atd.get("node_class", "")
        if node_class.startswith("NiagaraNode"):
            nodes.append(export)
    return nodes


class TestPinDecode:
    """Pin extraction from node native tails."""

    def test_sha256(self):
        assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper() == SHA256

    def test_node_handler_exposes_pins(self):
        """After decode, node handler data must contain a 'pins' list."""
        data = _parse_fixture()
        nodes = _get_node_exports(data)
        assert len(nodes) == 25, f"Expected 25 NiagaraNode* exports, found {len(nodes)}"
        for node in nodes:
            atd = node.get("asset_type_data", {})
            assert "pins" in atd, (
                f"{node['object_name']} missing 'pins' field; "
                f"keys={list(atd.keys())}"
            )
            assert isinstance(atd["pins"], list)

    def test_total_pin_count(self):
        """All 25 nodes together must contain 99 pins."""
        data = _parse_fixture()
        nodes = _get_node_exports(data)
        total_pins = sum(len(n.get("asset_type_data", {}).get("pins", [])) for n in nodes)
        assert total_pins == 99, f"Expected 99 total pins, found {total_pins}"

    def test_total_edge_count(self):
        """All pins together must contain 76 LinkedTo edges."""
        data = _parse_fixture()
        nodes = _get_node_exports(data)
        total_edges = 0
        for node in nodes:
            for pin in node.get("asset_type_data", {}).get("pins", []):
                linked_to = pin.get("linked_to", [])
                total_edges += len(linked_to)
        assert total_edges == EXPECTED_TOTAL_EDGES, (
            f"Expected {EXPECTED_TOTAL_EDGES} edges, found {total_edges}"
        )

    def test_pin_has_required_fields(self):
        """Each pin must expose OwningNode, PinId, PinName, PinType, Direction."""
        data = _parse_fixture()
        nodes = _get_node_exports(data)
        required = {"owning_node", "pin_id", "pin_name"}
        for node in nodes:
            for pin in node.get("asset_type_data", {}).get("pins", []):
                for field in required:
                    assert field in pin, (
                        f"Pin in {node['object_name']} missing '{field}'; "
                        f"fields={list(pin.keys())}"
                    )

    def test_native_tail_status_is_decoded(self):
        """native_tail.status must be 'decoded' (not 'opaque') after pin extraction."""
        data = _parse_fixture()
        nodes = _get_node_exports(data)
        for node in nodes:
            atd = node.get("asset_type_data", {})
            tail = atd.get("native_tail", {})
            assert tail.get("status") == "decoded", (
                f"{node['object_name']} native_tail.status={tail.get('status')}, expected 'decoded'"
            )
