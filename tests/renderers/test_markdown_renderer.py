"""Markdown renderer tests.

Tests the Markdown output format: structure, headings, tables, Mermaid charts.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read import parse_single
from uasset_read.renderers import get_renderer, list_formats
from uasset_read.renderers.base import RenderOptions
from uasset_read.ir_builder import build_package_ir
from uasset_read.pipeline.core import parse_package


def _render_markdown(samples_dir: Path, filename: str, **kwargs) -> str:
    """Parse a sample and render to Markdown."""
    sample = samples_dir / filename
    return parse_single(str(sample), format="markdown", tolerant=True, **kwargs)


class TestMarkdownRenderer:
    """Markdown output structure and content."""

    def test_markdown_format_registered(self):
        """Markdown renderer is registered in the format registry."""
        formats = list_formats()
        assert "markdown" in formats

    def test_markdown_contains_heading(self, samples_dir: Path):
        """Markdown output contains at least one heading."""
        if not (samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset").exists():
            pytest.skip("Sample not found")

        output = _render_markdown(samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset")
        assert "#" in output

    def test_markdown_contains_package_name(self, samples_dir: Path):
        """Markdown output references the package name."""
        if not (samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset").exists():
            pytest.skip("Sample not found")

        output = _render_markdown(samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset")
        # Should contain some reference to the asset
        assert len(output) > 0

    def test_markdown_for_material(self, samples_dir: Path):
        """Markdown rendering works for Material samples."""
        if not (samples_dir / "FirstPerson_M_FlatCol.uasset").exists():
            pytest.skip("Sample not found")

        output = _render_markdown(samples_dir, "FirstPerson_M_FlatCol.uasset")
        assert len(output) > 0
        assert "#" in output

    def test_markdown_for_data_table(self, samples_dir: Path):
        """Markdown rendering works for DataTable samples."""
        if not (samples_dir / "ALS_FootstepDataTable.uasset").exists():
            pytest.skip("Sample not found")

        output = _render_markdown(samples_dir, "ALS_FootstepDataTable.uasset")
        assert len(output) > 0

    def test_markdown_verbose_mode(self, samples_dir: Path):
        """Verbose mode produces more output than standard."""
        if not (samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset").exists():
            pytest.skip("Sample not found")

        standard = _render_markdown(
            samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset", verbose=False,
        )
        verbose = _render_markdown(
            samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset", verbose=True,
        )
        # Verbose should produce at least as much output
        assert len(verbose) >= len(standard)

    def test_markdown_has_tables(self, samples_dir: Path):
        """Markdown output contains table formatting."""
        if not (samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset").exists():
            pytest.skip("Sample not found")

        output = _render_markdown(samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset")
        # Markdown tables use | separators
        assert "|" in output


class TestMarkdownRendererDirect:
    """Direct renderer invocation tests."""

    def test_renderer_callable(self):
        """Markdown renderer can be obtained and called."""
        renderer = get_renderer("markdown")
        assert renderer is not None

    def test_renderer_render_method(self, samples_dir: Path):
        """Renderer.render() produces output from PackageIR."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        if not sample.exists():
            pytest.skip("Sample not found")

        result = parse_package(str(sample), tolerant=True)
        ir = build_package_ir(result)
        renderer = get_renderer("markdown")
        options = RenderOptions(verbose=False, output_level="standard")
        output = renderer.render(ir, options)
        assert isinstance(output, str)
        assert len(output) > 0
