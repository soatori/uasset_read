# tests/temp/test_resolved_references.py
"""Test resolved references in the new semantic JSON format."""

import json
from pathlib import Path

import pytest

from uasset_read import parse_single


def test_references_include_class_names():
    """References should include class_name and object_name."""
    sample = Path(__file__).resolve().parent.parent / "samples" / "FirstPerson_BP_FirstPersonCharacter.uasset"
    if not sample.exists():
        pytest.skip("sample not available")
    output = parse_single(str(sample), format="json", tolerant=True)
    data = json.loads(output)
    assert "references" in data, "Missing references field"
    refs = data["references"]
    assert isinstance(refs, list), "references should be a list"
    assert len(refs) > 0, "references should not be empty"
    for ref in refs:
        assert "kind" in ref, "reference missing kind"
        assert "class_name" in ref, "reference missing class_name"
        assert "object_name" in ref, "reference missing object_name"


def test_references_have_valid_kinds():
    """References should have valid kind values."""
    sample = Path(__file__).resolve().parent.parent / "samples" / "FirstPerson_BP_FirstPersonCharacter.uasset"
    if not sample.exists():
        pytest.skip("sample not available")
    output = parse_single(str(sample), format="json", tolerant=True)
    data = json.loads(output)
    refs = data["references"]
    valid_kinds = {"export", "import"}
    for ref in refs:
        assert ref["kind"] in valid_kinds, f"Invalid kind: {ref['kind']}"
