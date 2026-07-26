"""Tests for JSON output quality — status, diagnostics, truncation markers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read.ir_builder import build_package_ir
from uasset_read.parse_uasset import parse_package
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.validators import VALID_PARSE_STATUSES

_SAMPLE_DIR = Path(__file__).resolve().parent.parent / "samples"


class TestJSONOutputStatus:
    """Verify JSON output contains correct status and diagnostics fields."""

    def _render_json(self, sample_path: Path) -> dict:
        """Parse a sample and render to JSON dict."""
        result = parse_package(str(sample_path))
        ir = build_package_ir(result)
        renderer = JSONRenderer()
        options = RenderOptions(output_level="standard")
        json_str = renderer.render(ir, options)
        return json.loads(json_str)

    def test_all_samples_have_status_field(self):
        """Every sample's JSON output must have a top-level status object."""
        samples = list(_SAMPLE_DIR.glob("*.uasset"))
        assert len(samples) > 0, "No samples found"

        for sample in samples:
            data = self._render_json(sample)
            assert "status" in data, f"{sample.name}: missing 'status' field"
            status_obj = data["status"]
            assert isinstance(status_obj, dict), (
                f"{sample.name}: 'status' is not a dict"
            )
            assert "status" in status_obj, (
                f"{sample.name}: status object missing inner 'status' field"
            )
            assert status_obj["status"] in ("success", "partial", "failed"), (
                f"{sample.name}: invalid status '{status_obj['status']}'"
            )

    def test_all_exports_have_parse_status(self):
        """Exports with non-success parse_status must have it in JSON output."""
        samples = list(_SAMPLE_DIR.glob("*.uasset"))
        for sample in samples:
            data = self._render_json(sample)
            for i, export in enumerate(data.get("exports", [])):
                if "parse_status" in export:
                    assert export["parse_status"] in VALID_PARSE_STATUSES, (
                        f"{sample.name} export[{i}]: invalid parse_status "
                        f"'{export['parse_status']}'"
                    )

    def test_diagnostics_field_structure(self):
        """Diagnostics must be a list of objects with required fields."""
        samples = list(_SAMPLE_DIR.glob("*.uasset"))
        for sample in samples:
            data = self._render_json(sample)
            if "diagnostics" in data:
                assert isinstance(data["diagnostics"], list), (
                    f"{sample.name}: diagnostics is not a list"
                )
                for diag in data["diagnostics"]:
                    assert isinstance(diag, dict), (
                        f"{sample.name}: diagnostic entry is not a dict"
                    )
                    assert "kind" in diag, (
                        f"{sample.name}: diagnostic missing 'kind' field"
                    )

    def test_error_message_present_on_failure(self):
        """Status object must have a message when status is not 'success'."""
        samples = list(_SAMPLE_DIR.glob("*.uasset"))
        for sample in samples:
            data = self._render_json(sample)
            status_obj = data.get("status", {})
            if status_obj.get("status") in ("partial", "failed"):
                assert "message" in status_obj, (
                    f"{sample.name}: status is '{status_obj.get('status')}' "
                    "but no message in status object"
                )
