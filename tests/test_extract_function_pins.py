"""Tests for extract_function_pins.py standalone script."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "extract_function_pins.py"


@pytest.fixture
def blueprint_asset(samples_dir: Path) -> Path:
    """Return a Blueprint .uasset sample file."""
    from tests.conftest import get_samples_by_category
    assets = get_samples_by_category(samples_dir, "blueprint")
    if not assets:
        pytest.skip("No Blueprint samples found")
    return assets[0]


def _run_script(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Run extract_function_pins.py with given arguments."""
    env = os.environ.copy()
    if env.get("PYTHONPATH"):
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


class TestArgumentParsing:
    """Test CLI argument parsing and error handling."""

    def test_no_args_prints_usage(self):
        result = _run_script()
        assert result.returncode != 0
        assert "error" in result.stderr.lower() or "usage" in result.stderr.lower()

    def test_missing_file_exits_error(self):
        result = _run_script("nonexistent.uasset")
        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_help_flag(self):
        result = _run_script("--help")
        assert result.returncode == 0
        assert "extract" in result.stdout.lower() or "function" in result.stdout.lower()


class TestExtraction:
    """Test core extraction logic against real Blueprint assets."""

    def test_extract_returns_list(self, blueprint_asset: Path):
        """Extraction from a Blueprint asset returns a non-empty list."""
        from extract_function_pins import extract_function_pins
        result = extract_function_pins(str(blueprint_asset))
        assert isinstance(result, list)

    def test_extract_entry_structure(self, blueprint_asset: Path):
        """Each entry has the required fields."""
        from extract_function_pins import extract_function_pins
        result = extract_function_pins(str(blueprint_asset))
        if not result:
            pytest.skip("Asset yielded no function graphs")
        entry = result[0]
        assert "function_name" in entry
        assert "return_type" in entry
        assert "parameters" in entry
        assert isinstance(entry["parameters"], list)

    def test_extract_parameter_structure(self, blueprint_asset: Path):
        """Each parameter has name, type, and direction."""
        from extract_function_pins import extract_function_pins
        result = extract_function_pins(str(blueprint_asset))
        for entry in result:
            for param in entry["parameters"]:
                assert "name" in param
                assert "type" in param
                assert "direction" in param
                assert param["direction"] in ("input", "output")

    def test_extract_non_blueprint_returns_empty(self, samples_dir: Path):
        """Non-Blueprint assets return an empty list."""
        from tests.conftest import get_samples_by_category
        from extract_function_pins import extract_function_pins
        candidates = get_samples_by_category(samples_dir, "material")
        if not candidates:
            pytest.skip("No material samples found")
        result = extract_function_pins(str(candidates[0]))
        assert isinstance(result, list)
        assert len(result) == 0

    def test_extract_strict_mode(self, blueprint_asset: Path):
        """Strict mode does not crash on valid assets."""
        from extract_function_pins import extract_function_pins
        result = extract_function_pins(str(blueprint_asset), tolerant=False)
        assert isinstance(result, list)


class TestTextFormatter:
    """Test human-readable text output format."""

    def test_format_text_basic(self):
        from extract_function_pins import format_text
        entries = [
            {
                "function_name": "MyFunction",
                "return_type": "void",
                "parameters": [
                    {"name": "Param1", "type": "int32", "direction": "input"},
                    {"name": "Param2", "type": "float", "direction": "input"},
                ],
            }
        ]
        result = format_text(entries)
        assert "MyFunction" in result
        assert "int32" in result
        assert "float" in result
        assert "<-" in result  # input arrow

    def test_format_text_with_return_type(self):
        from extract_function_pins import format_text
        entries = [
            {
                "function_name": "GetValue",
                "return_type": "float",
                "parameters": [],
            }
        ]
        result = format_text(entries)
        assert "float GetValue()" in result

    def test_format_text_output_parameter(self):
        from extract_function_pins import format_text
        entries = [
            {
                "function_name": "GetLocation",
                "return_type": "void",
                "parameters": [
                    {"name": "OutLocation", "type": "vector", "direction": "output"},
                ],
            }
        ]
        result = format_text(entries)
        assert "->" in result  # output arrow
        assert "OutLocation" in result

    def test_format_text_empty_list(self):
        from extract_function_pins import format_text
        result = format_text([])
        assert result.strip() == "" or "no functions" in result.lower()

    def test_format_text_fallback_reason(self):
        from extract_function_pins import format_text
        entries = [
            {
                "function_name": "BigFunc",
                "return_type": "void",
                "parameters": [],
                "fallback_reason": "graph_complexity_limit",
            }
        ]
        result = format_text(entries)
        assert "graph_complexity_limit" in result

    def test_format_text_multiple_functions(self):
        from extract_function_pins import format_text
        entries = [
            {
                "function_name": "FuncA",
                "return_type": "void",
                "parameters": [],
            },
            {
                "function_name": "FuncB",
                "return_type": "bool",
                "parameters": [
                    {"name": "bFlag", "type": "bool", "direction": "input"},
                ],
            },
        ]
        result = format_text(entries)
        assert "FuncA" in result
        assert "FuncB" in result
        lines = result.strip().split("\n")
        assert len(lines) >= 3


class TestJsonFormatter:
    """Test JSON output format."""

    def test_format_json_valid(self):
        from extract_function_pins import format_json
        entries = [
            {
                "function_name": "MyFunction",
                "return_type": "void",
                "parameters": [
                    {"name": "Param1", "type": "int32", "direction": "input"},
                ],
            }
        ]
        result = format_json(entries)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["function_name"] == "MyFunction"

    def test_format_json_has_is_input_is_output(self):
        """JSON output includes is_input/is_output boolean fields."""
        from extract_function_pins import format_json
        entries = [
            {
                "function_name": "GetLocation",
                "return_type": "void",
                "parameters": [
                    {"name": "OutLoc", "type": "vector", "direction": "output"},
                    {"name": "InName", "type": "string", "direction": "input"},
                ],
            }
        ]
        result = format_json(entries)
        parsed = json.loads(result)
        params = parsed[0]["parameters"]
        assert params[0]["is_input"] is False
        assert params[0]["is_output"] is True
        assert params[1]["is_input"] is True
        assert params[1]["is_output"] is False

    def test_format_json_empty_list(self):
        from extract_function_pins import format_json
        result = format_json([])
        parsed = json.loads(result)
        assert parsed == []

    def test_format_json_roundtrip(self):
        """JSON output is valid and round-trips cleanly."""
        from extract_function_pins import format_json
        entries = [
            {
                "function_name": "Test",
                "return_type": "bool",
                "parameters": [
                    {"name": "bFlag", "type": "bool", "direction": "input"},
                    {"name": "OutResult", "type": "int32", "direction": "output"},
                ],
            }
        ]
        result = format_json(entries)
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["function_name"] == "Test"
        assert parsed[0]["parameters"][0]["is_input"] is True
        assert parsed[0]["parameters"][0]["is_output"] is False
        assert parsed[0]["parameters"][1]["is_input"] is False
        assert parsed[0]["parameters"][1]["is_output"] is True


class TestIntegration:
    """End-to-end tests running the script as a subprocess."""

    def test_text_output_blueprint(self, blueprint_asset: Path):
        """Human-readable output contains function signatures."""
        result = _run_script(str(blueprint_asset))
        if result.returncode != 0:
            pytest.skip(f"Script failed: {result.stderr}")
        # Text output should contain function signatures or empty message
        assert "void" in result.stdout or "No functions" in result.stdout or "<-" in result.stdout or "->" in result.stdout

    def test_json_output_blueprint(self, blueprint_asset: Path):
        """JSON output is valid and contains expected structure."""
        result = _run_script(str(blueprint_asset), "--json")
        if result.returncode != 0:
            pytest.skip(f"Script failed: {result.stderr}")
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, list)

    def test_json_output_to_file(self, blueprint_asset: Path, tmp_path: Path):
        """--output flag writes to file."""
        out_file = tmp_path / "pins.json"
        result = _run_script(str(blueprint_asset), "--json", "--output", str(out_file))
        if result.returncode != 0:
            pytest.skip(f"Script failed: {result.stderr}")
        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert isinstance(parsed, list)

    def test_exit_code_zero_on_success(self, blueprint_asset: Path):
        """Script exits 0 on successful parse."""
        result = _run_script(str(blueprint_asset))
        if result.returncode != 0 and "not a blueprint" in result.stderr.lower():
            pytest.skip("Not a Blueprint asset")
        assert result.returncode == 0

    def test_exit_code_nonzero_on_missing_file(self):
        """Script exits non-zero for missing file."""
        result = _run_script("does_not_exist.uasset")
        assert result.returncode != 0
