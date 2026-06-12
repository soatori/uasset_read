from __future__ import annotations

import warnings

import pytest

from uasset_read.graph.flow_builder import (
    build_execution_flow_entries,
    build_execution_flows,
)
from uasset_read.models.core import UEdGraph


def _empty_graph() -> UEdGraph:
    return UEdGraph(graph_name="EventGraph", graph_class="EdGraph")


def test_build_execution_flow_entries_does_not_warn():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert build_execution_flow_entries(_empty_graph()) == []

    assert not [
        warning
        for warning in caught
        if issubclass(warning.category, DeprecationWarning)
    ]


def test_build_execution_flows_still_warns():
    with pytest.deprecated_call(match="build_execution_flows\\(\\) is deprecated"):
        assert build_execution_flows(_empty_graph()) == []
