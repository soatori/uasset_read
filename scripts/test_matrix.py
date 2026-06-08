#!/usr/bin/env python3
"""统一测试矩阵入口。

目的不是替代 pytest，而是把仓库里的测试按目标分层，给本地和 CI
一个稳定的调用方式。

用法:
    python scripts/test_matrix.py smoke
    python scripts/test_matrix.py unit
    python scripts/test_matrix.py integration
    python scripts/test_matrix.py regression
    python scripts/test_matrix.py quality
    python scripts/test_matrix.py all
    python scripts/test_matrix.py smoke -- -k blueprint
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"


SUITES: dict[str, list[str]] = {
    "smoke": [
        "tests/test_core_api.py",
        "tests/test_ir_structures.py",
        "tests/test_renderers.py",
        "tests/test_truncated_file.py",
        "tests/test_version_compatibility.py",
        "tests/test_unknown_property_fallback.py",
        "tests/test_tolerant_early_parse_diagnostics.py",
        "tests/test_package_summary_fields.py",
        "tests/test_parse_package_core.py",
    ],
    "unit": [
        "tests",
        "-m",
        "not integration and not quality and not regression and not slow",
    ],
    "integration": ["tests", "-m", "integration"],
    "regression": ["tests", "-m", "regression"],
    "quality": ["tests", "-m", "quality"],
    "all": ["tests"],
}


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = str(SRC_DIR)
    if env.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description="Run curated pytest suites")
    parser.add_argument("suite", choices=sorted(SUITES.keys()))
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments passed through to pytest after --",
    )
    args = parser.parse_args()

    passthrough = args.pytest_args
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    cmd = [sys.executable, "-m", "pytest", *SUITES[args.suite], *passthrough]
    print("Running:", " ".join(cmd), flush=True)
    completed = subprocess.run(cmd, cwd=ROOT, env=build_env())
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
