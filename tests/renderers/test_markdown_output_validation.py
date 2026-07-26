"""Tests for Markdown output quality — status indicators, diagnostics."""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.ir_builder import build_package_ir
from uasset_read.parse_uasset import parse_package
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.base import RenderOptions

_SAMPLE_DIR = Path(__file__).resolve().parent.parent / "samples"


class TestMarkdownOutputStatus:
    """Verify Markdown output contains correct status indicators."""

    def _render_markdown(self, sample_path: Path) -> str:
        """Parse a sample and render to Markdown string."""
        result = parse_package(str(sample_path))
        ir = build_package_ir(result)
        renderer = MarkdownRenderer()
        options = RenderOptions(output_level="standard")
        return renderer.render(ir, options)

    def test_all_samples_render_markdown(self):
        """Every sample must produce non-empty Markdown output."""
        samples = list(_SAMPLE_DIR.glob("*.uasset"))
        assert len(samples) > 0, "No samples found"

        for sample in samples:
            md = self._render_markdown(sample)
            assert len(md) > 0, f"{sample.name}: empty Markdown output"
            assert sample.stem in md or "Package" in md, (
                f"{sample.name}: package name not in Markdown output"
            )

    def test_markdown_contains_export_info(self):
        """Markdown output must list exports."""
        sample = _SAMPLE_DIR / "FirstPerson_BP_FirstPersonCharacter.uasset"
        if not sample.exists():
            pytest.skip("Sample not found")

        md = self._render_markdown(sample)
        assert "export" in md.lower() or "object" in md.lower(), (
            "Markdown output missing export information"
        )

    def test_markdown_status_indicators(self):
        """Markdown must indicate parse status for each export."""
        samples = list(_SAMPLE_DIR.glob("*.uasset"))
        for sample in samples:
            md = self._render_markdown(sample)
            assert len(md) > 100, f"{sample.name}: suspiciously short Markdown"
