"""Phase 69 Wave 4 - Full regression tests."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


@pytest.fixture(autouse=True)
def reset_registry():
    """Ensure clean registry state for these tests."""
    from uasset_read.n2c.processor_registry import N2CProcessorRegistry
    N2CProcessorRegistry.reset()
    yield
    N2CProcessorRegistry.reset()


def test_all_existing_tests_pass():
    """Run full test suite via subprocess, assert zero failures.

    Skipped when already running inside a subprocess (prevent recursion).
    """
    if os.environ.get("UASSET_READ_SUBPROCESS_REGRESSION"):
        pytest.skip("Already running in subprocess regression mode")

    env = os.environ.copy()
    env["UASSET_READ_SUBPROCESS_REGRESSION"] = "1"

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    # Check for failures in output
    clean_output = _strip_ansi(result.stdout)
    failed_match = re.search(r'(\d+)\s+failed', clean_output)
    if failed_match:
        n_failures = int(failed_match.group(1))
        assert n_failures == 0, f"Test failures detected:\n{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, f"pytest returned non-zero exit code:\n{result.stdout}\n{result.stderr}"


def test_n2c_module_imports():
    """Verify all n2c modules are importable."""
    from uasset_read.n2c import N2CNodeDefinition
    from uasset_read.n2c.processor_base import N2CNodeProcessor
    from uasset_read.n2c.processor_registry import N2CProcessorRegistry
    from uasset_read.n2c.processors import register_all_processors
    from uasset_read.n2c.compat import definition_to_node_dict, definition_to_trace_node_info
    from uasset_read.graph.flow_builder import build_execution_flows, format_node_dict, _trace_execution_from_event

    # Verify they are the expected types
    assert callable(N2CNodeDefinition)
    assert callable(N2CNodeProcessor)
    assert callable(N2CProcessorRegistry)
    assert callable(register_all_processors)
    assert callable(definition_to_node_dict)
    assert callable(definition_to_trace_node_info)
    assert callable(build_execution_flows)
    assert callable(format_node_dict)
    assert callable(_trace_execution_from_event)


def test_processor_registry_initialized():
    """Verify register_all_processors() works and registry has processors."""
    from uasset_read.n2c.processors import register_all_processors
    from uasset_read.n2c.processor_registry import N2CProcessorRegistry

    register_all_processors()
    registry = N2CProcessorRegistry.get_instance()

    # Should have multiple processors registered
    assert len(registry._processors) > 0, "No processors registered"
    # Should have a fallback processor
    assert registry._fallback is not None, "No fallback processor set"

    # Verify known processor types are registered
    processor_types = [type(p).__name__ for p in registry._processors.values()]
    assert "CallFunctionProcessor" in processor_types
    assert "EventProcessor" in processor_types
    assert "FlowControlProcessor" in processor_types
    assert "VariableProcessor" in processor_types
    assert "CastProcessor" in processor_types
    assert "FunctionEntryProcessor" in processor_types
