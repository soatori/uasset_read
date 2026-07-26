"""Benchmark the public package parsing contract."""

import pytest

from uasset_read import parse_uasset_with_linker


@pytest.mark.benchmark
def test_parse_public_contract(blueprint_sample, measure):
    with measure("parse"):
        result = parse_uasset_with_linker(
            str(blueprint_sample),
            tolerant=True,
            force_full_parse=True,
        )

    assert result.is_success, result.errors
    assert not result.errors
    assert result.summary is not None
    assert result.linker is not None
    assert result.name_map
    assert result.export_map
    assert result.graphs
    assert any(node.pins for graph in result.graphs for node in graph.nodes)
