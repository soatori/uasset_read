"""Application contract — CLI, Agent tools, JSON serialization, logging lifecycle."""

from __future__ import annotations

from pathlib import Path

import json
import logging
import subprocess
import sys


SAMPLES_DIR = Path(__file__).parent / "samples"
SAMPLE = str(SAMPLES_DIR / "ALS_FootstepDataTable.uasset")


class TestCLI:
    def test_cli_v2_runs(self):
        result = subprocess.run(
            [sys.executable, "-m", "uasset_read", "--v2", SAMPLE],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr[:500]}"
        data = json.loads(result.stdout)
        assert data["format"] == "uasset_read.package"

    def test_cli_v2_has_objects(self):
        result = subprocess.run(
            [sys.executable, "-m", "uasset_read", "--v2", SAMPLE],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        assert len(data["objects"]) > 0

    def test_cli_no_v2_defaults_to_legacy(self):
        result = subprocess.run(
            [sys.executable, "-m", "uasset_read", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "--v2" in result.stdout


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
        result = list_objects(bp_sample, limit=3)
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
