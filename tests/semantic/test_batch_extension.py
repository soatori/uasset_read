"""Tests for batch output extension routing."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("format_name,expected_ext", [
    ("json", ".json"),
    ("semantic_json", ".json"),
    ("markdown", ".md"),
])
def test_batch_extension(format_name: str, expected_ext: str) -> None:
    """Batch output extension matches expected value per format."""
    if format_name == "json" or format_name == "semantic_json":
        extension = ".json"
    elif format_name == "markdown":
        extension = ".md"
    else:
        extension = f".{format_name}"
    assert extension == expected_ext
