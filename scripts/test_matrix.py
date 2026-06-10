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
        "not integration and not quality and not regression and not slow and not auxiliary and not acceptance",
    ],
    "integration": ["tests", "-m", "integration"],
    "regression": ["tests", "-m", "regression"],
    "quality": ["tests", "-m", "quality"],
    "auxiliary": [
        "tests/test_api_cleanup.py",
        "tests/test_quality_stats.py",
        "tests/test_cue4parse_gap_completion.py",
    ],
    "acceptance": [
        "tests/test_acceptance.py",
    ],
    "all": [
        "tests",
        "-m",
        "not large",  # 默认排除大资产测试
    ],
    "all-with-large": [
        "tests",  # 包含所有测试（含 large）
    ],
}

# 这些 suite 涉及大量资产加载，强制串行防止多进程 OOM
_SERIAL_SUITES = {"all", "all-with-large"}


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = str(SRC_DIR)
    if env.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath
    return env


def _has_xdist() -> bool:
    """检查 pytest-xdist 是否已安装（轻量 importlib 检查）。"""
    import importlib.util
    return importlib.util.find_spec("xdist") is not None


def _strip_xdist_workers(args: list[str]) -> list[str]:
    """移除 passthrough 中的 -n N / -nN / --numprocesses N，避免与串行保护冲突。"""
    cleaned: list[str] = []
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in ("-n", "--numprocesses"):
            skip_next = True  # 跳过后面的数字
            continue
        if arg.startswith("-n") and arg[2:].lstrip().isdigit():
            continue  # -n4 形式
        if arg.startswith("--numprocesses="):
            continue
        cleaned.append(arg)
    return cleaned


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

    # 检测 --include-large（可能在 passthrough 中，也可能作为顶层参数）
    include_large = "--include-large" in passthrough
    if include_large:
        passthrough = [a for a in passthrough if a != "--include-large"]

    extra_args: list[str] = []

    # --include-large 透传给 pytest；当传 --include-large 时，移除 -m not large 让 conftest 处理 skip
    suite_args = list(SUITES[args.suite])
    if include_large:
        extra_args.append("--include-large")
        # 仅当 suite 含 "-m", "not large" 时移除，避免与 conftest skip 逻辑冲突
        if "-m" in suite_args and "not large" in suite_args:
            idx_m = suite_args.index("-m")
            idx_nl = suite_args.index("not large")
            if idx_nl == idx_m + 1:
                suite_args = suite_args[:idx_m] + suite_args[idx_nl + 1:]

    # 串行保护：all / all-with-large 强制 -n 1，覆盖用户传入的 -n N
    if args.suite in _SERIAL_SUITES:
        passthrough = _strip_xdist_workers(passthrough)
        if _has_xdist():
            extra_args.append("-n")
            extra_args.append("1")
            print(
                f"[test_matrix] suite '{args.suite}' forces -n 1 "
                f"(multi-process xdist OOM risk — see docs/guides/testing-concurrency.md)",
                flush=True,
            )
        else:
            print(
                f"[test_matrix] suite '{args.suite}' runs single-process "
                f"(pytest-xdist not installed — no parallel execution possible)",
                flush=True,
            )

    cmd = [sys.executable, "-m", "pytest", *suite_args, *extra_args, *passthrough]
    print("Running:", " ".join(cmd), flush=True)
    completed = subprocess.run(cmd, cwd=ROOT, env=build_env())
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
