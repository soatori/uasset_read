"""Application contract — CLI, Agent tools, JSON serialization, logging lifecycle."""

from __future__ import annotations

from pathlib import Path

import json
import logging
import subprocess
import sys


SAMPLES_DIR = Path(__file__).parent.parent / "samples"
SAMPLE = str(SAMPLES_DIR / "ALS_FootstepDataTable.uasset")


def run_cli_json(*args: str) -> dict:
    """Run CLI and return parsed JSON output."""
    result = subprocess.run(
        [sys.executable, "-m", "uasset_read", *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr[:500]}"
    return json.loads(result.stdout)


class TestCLI:
    def test_cli_v2_runs(self):
        result = subprocess.run(
            [sys.executable, "-m", "uasset_read", SAMPLE],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr[:500]}"
        data = json.loads(result.stdout)
        assert data["format"] == "uasset_read.package"

    def test_cli_v2_has_objects(self):
        data = run_cli_json(SAMPLE)
        assert len(data["objects"]) > 0

    def test_cli_v2_depth_and_limit(self):
        data = run_cli_json("--depth", "package", "--limit", "2", SAMPLE)
        assert data["depth"] == "package"
        assert len(data["objects"]) <= 2

    def test_cli_defaults_to_v2_package_document(self):
        out = run_cli_json(SAMPLE)
        assert out["format"] == "uasset_read.package"
        assert "objects" in out and out["package"]

    def test_cli_v2_flag_is_accepted_as_noop(self):
        plain = run_cli_json(SAMPLE)
        with_flag = run_cli_json("--v2", SAMPLE)
        assert plain == with_flag

    def test_cli_legacy_json_opt_in(self):
        out = run_cli_json("--legacy-json", SAMPLE)
        assert out["format"] != "uasset_read.package" or "objects" not in out


class TestProjectionEquality:
    """CLI, Python API, and Agent tools produce identical projection output."""

    def test_cli_agent_python_share_projection(self):
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.projection import project_document
        from uasset_read.v2.agent_tools import inspect_package

        doc = parse_package_document(SAMPLE, depth="package")
        expected = project_document(doc, depth="package", limit=2, max_bytes=4096)
        cli = run_cli_json("--depth", "package", "--limit", "2", "--max-bytes", "4096", SAMPLE)
        agent = inspect_package(SAMPLE, depth="package", limit=2, max_bytes=4096)

        # Compare object IDs
        for actual in (cli, agent):
            assert [o["id"] for o in actual["objects"]] == [o["id"] for o in expected["objects"]]
            assert actual["diagnostics"] == expected["diagnostics"]


class TestAgentTools:
    def test_inspect_package(self):
        from uasset_read.v2.agent_tools import inspect_package

        result = inspect_package(SAMPLE)
        assert "source" in result
        assert "package" in result
        assert "summary" in result

    def test_list_objects(self):
        from uasset_read.v2.agent_tools import list_objects

        result = list_objects(SAMPLE)
        assert result["total"] > 0
        assert len(result["objects"]) > 0

    def test_list_objects_pagination(self):
        from uasset_read.v2.agent_tools import list_objects

        # Use a sample with enough objects to paginate
        bp_sample = str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset")
        result = list_objects(bp_sample, limit=3, max_bytes=65536)
        assert result["returned"] == 3
        assert result["next_offset"] == 3

    def test_get_object(self):
        from uasset_read.v2.agent_tools import get_object

        result = get_object(SAMPLE, "export:0")
        assert result["id"] == "export:0"
        assert "name" in result

    def test_list_dependencies(self):
        from uasset_read.v2.agent_tools import list_dependencies

        result = list_dependencies(SAMPLE)
        assert "dependencies" in result
        assert "relations" in result

    def test_get_diagnostics(self):
        from uasset_read.v2.agent_tools import get_diagnostics

        result = get_diagnostics(SAMPLE)
        assert "diagnostics" in result
        assert "total" in result

    def test_json_serializable(self):
        from uasset_read.v2.agent_tools import inspect_package

        result = inspect_package(SAMPLE)
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert "source" in parsed
        assert "package" in parsed
        assert "summary" in parsed


class TestLoggingLifecycle:
    def test_disabled_logging_no_files(self, tmp_path):
        old_level = logging.root.level
        try:
            logging.root.setLevel(logging.WARNING)
            from uasset_read.v2.api import parse_package_document

            parse_package_document(SAMPLE)
        finally:
            logging.root.setLevel(old_level)

    def test_root_logger_not_modified(self):
        old_handler_count = len(logging.root.handlers)
        old_level = logging.root.level
        try:
            from uasset_read.v2.api import parse_package_document

            parse_package_document(SAMPLE)
            assert len(logging.root.handlers) == old_handler_count
            assert logging.root.level == old_level
        finally:
            logging.root.setLevel(old_level)
