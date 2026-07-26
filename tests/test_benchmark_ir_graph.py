"""Benchmark the parsed package to IR and graph pipeline."""

import pytest

from uasset_read import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir


@pytest.mark.benchmark
def test_ir_graph_public_contract(blueprint_sample, measure):
    with measure("ir_graph"):
        result = parse_uasset_with_linker(
            str(blueprint_sample),
            tolerant=True,
            force_full_parse=True,
        )
        package_ir = build_package_ir(result)

    assert result.is_success, result.errors
    assert package_ir.exports
    assert package_ir.blueprint is not None
    assert package_ir.variables
    assert package_ir.function_graphs
    assert all(graph.get("function_name") for graph in package_ir.function_graphs)
    assert any(
        chain.get("nodes")
        for graph in package_ir.function_graphs
        for chain in graph.get("execution_chains", [])
    )
