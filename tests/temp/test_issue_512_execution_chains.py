import json
from pathlib import Path

import jsonschema
import pytest

from uasset_read import parse_single


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "FirstPerson_BP_FirstPersonCharacter.uasset"
SCHEMA = json.loads((ROOT / "schemas" / "package.schema.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("output_level", ["standard", "debug"])
def test_first_person_graphs_publish_schema_valid_execution_chains(output_level: str) -> None:
    data = json.loads(parse_single(
        str(SAMPLE), format="json", output_level=output_level,
        force_full_parse=True, log_enabled=False,
    ))
    graphs = [graph for export in data["exports"] for graph in export.get("graphs", [])]

    assert graphs
    assert all(isinstance(graph["nodes"], list) for graph in graphs)
    assert any(
        pin["linked_to"]
        for graph in graphs
        for node in graph["nodes"]
        for pin in node["pins"]
    )
    chains = [chain for graph in graphs for chain in graph["execution_chains"]]
    assert chains
    assert all(
        isinstance(chain["start_event"], str)
        and chain["start_event"]
        and isinstance(chain["chains"], list)
        and chain["chains"]
        and all(isinstance(segment, str) and segment for segment in chain["chains"])
        and isinstance(chain["has_cycle"], bool)
        for chain in chains
    )
    jsonschema.validate(data, SCHEMA)
