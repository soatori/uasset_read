# tests/test_single_output.py
import json
import pytest

from uasset_read.projections.registry import ProjectorRegistry
from uasset_read.projections.bundle import write_projected_document


def test_projections_are_embedded_and_have_no_default_output_paths(document):
    projections = ProjectorRegistry.default().project_document(document)
    assert projections
    assert all(item.embedded for item in projections)
    assert all(item.content is not None or item.status == "unavailable" for item in projections)


def test_single_document_writer_writes_canonical_document(document, tmp_path):
    output = write_projected_document(document, tmp_path / "Asset.json")
    assert output.name == "Asset.json"
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["package"]
    assert "objects" in payload
    assert "projections" in payload


def test_writer_rejects_a_limit_below_the_mandatory_envelope(document, tmp_path):
    from uasset_read.projections.bundle import minimum_canonical_envelope_bytes, OutputBudgetError

    minimum = minimum_canonical_envelope_bytes(document)
    with pytest.raises(OutputBudgetError):
        write_projected_document(document, tmp_path / "TooSmall.json", max_main_bytes=minimum - 1)


def test_writer_budget_uses_the_same_registry_for_minimum(document, tmp_path):
    """Custom-registry budgets must not compare against a default-registry envelope."""
    from uasset_read.projections.bundle import (
        minimum_canonical_envelope_bytes,
        write_projected_document,
    )

    custom = ProjectorRegistry()  # no projectors → smaller projection set
    custom_minimum = minimum_canonical_envelope_bytes(document, registry=custom)
    output = write_projected_document(
        document,
        tmp_path / "CustomFit.json",
        max_main_bytes=custom_minimum,
        registry=custom,
    )
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["projections"] == []
