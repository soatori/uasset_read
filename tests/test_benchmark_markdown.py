"""Benchmark the user-visible Markdown output contract."""

import pytest

from uasset_read import parse_single


@pytest.mark.benchmark
def test_markdown_output_public_contract(blueprint_sample, measure):
    with measure("markdown"):
        output = parse_single(
            str(blueprint_sample),
            format="markdown",
            tolerant=True,
            force_full_parse=True,
            include_function_graphs=True,
        )

    assert output.startswith("# BP_FirstPersonCharacter\n")
    for heading in (
        "## Asset Overview",
        "## Status",
        "## Exports",
        "## Event Graph",
        "## Functions",
        "## Variables",
    ):
        assert heading in output
    assert "```mermaid" in output
