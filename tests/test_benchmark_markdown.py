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
        "## Exports",
        "## Event Graph",
        "## Functions",
        "## Variables",
    ):
        assert heading in output
    assert "## Status" not in output
    assert "```mermaid" in output


def test_markdown_status_section_is_reserved_for_non_success_diagnostics():
    """Successful Markdown stays concise; degraded packages retain diagnostics."""
    from uasset_read.models.ir import DiagnosticsDataIR, PackageHeaderIR, PackageIR
    from uasset_read.renderers.base import RenderOptions
    from uasset_read.renderers.markdown_renderer import MarkdownRenderer

    ir = PackageIR(
        header=PackageHeaderIR(
            package_name="/Game/Test/Degraded",
            package_class="BlueprintGeneratedClass",
            package_flags=0,
            total_export_count=0,
            total_import_count=0,
            ue_version="5.8",
            saved_hash=b"",
            total_properties=0,
            total_name_entries=0,
        ),
        name_map=(),
        imports=[],
        exports=[],
        linker=None,
        diagnostics_data=DiagnosticsDataIR(
            status="partial",
            status_message="Recovered with warnings",
            errors=["Property range mismatch"],
            warnings=["Native field retained"],
        ),
    )

    output = MarkdownRenderer().render(ir, RenderOptions())

    assert "## Status" in output
    assert "**PARTIAL**: Recovered with warnings" in output
    assert "### Errors" in output
    assert "- Property range mismatch" in output
    assert "### Warnings" in output
    assert "- Native field retained" in output
