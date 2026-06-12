#!/usr/bin/env python3
"""Unified test entrypoint for uasset_read."""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_SAMPLE_ROOT = Path(r"E:\Develop\lib\UnrealEngine\Samples")
ASSET_SUITES = {"assets", "acceptance", "quality", "all"}

PYTEST_SUITES: dict[str, list[str]] = {
    "smoke": ["tests", "-m", "smoke"],
    "unit": ["tests", "-m", "smoke or unit"],
    "assets": ["tests", "-m", "assets"],
    "quality": ["tests", "-m", "quality"],
    "acceptance": ["tests", "-m", "acceptance"],
    "all": ["tests"],
}


@dataclass
class CompatAssetResult:
    asset_path: str
    return_code: int
    status: str
    valid_json: bool
    diagnostics_count: int
    failure_stage: str
    elapsed_seconds: float
    error_message: str = ""


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = str(SRC_DIR)
    if env.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath
    return env


def resolve_sample_root(value: str | None) -> Path:
    if value:
        return Path(value)
    if os.environ.get("UE_SAMPLE_ROOT"):
        return Path(os.environ["UE_SAMPLE_ROOT"])
    return DEFAULT_SAMPLE_ROOT


def require_sample_root(sample_root: Path, allow_missing: bool) -> bool:
    if sample_root.exists():
        return True
    message = (
        f"UE sample root not found: {sample_root}\n"
        "Set UE_SAMPLE_ROOT, pass --sample-root, or use --allow-missing-assets."
    )
    if allow_missing:
        print(f"[uasset_test] {message}", file=sys.stderr)
        return False
    print(f"[uasset_test] {message}", file=sys.stderr)
    return False


def discover_assets(sample_root: Path) -> list[Path]:
    if not sample_root.exists():
        return []
    return sorted(
        p for p in sample_root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".uasset", ".umap"}
    )


def split_pytest_args(raw: list[str]) -> list[str]:
    if not raw:
        return []
    if raw[0] == "--":
        return raw[1:]
    return raw


def run_pytest_suite(args: argparse.Namespace) -> int:
    suite_args = list(PYTEST_SUITES[args.suite])
    sample_root = resolve_sample_root(args.sample_root)
    if args.suite in ASSET_SUITES and not require_sample_root(sample_root, args.allow_missing_assets):
        return 0 if args.allow_missing_assets else 2

    pytest_args = split_pytest_args(args.pytest_args)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *suite_args,
        "--sample-root",
        str(sample_root),
    ]
    if args.allow_missing_assets:
        cmd.append("--allow-missing-assets")
    cmd.extend(pytest_args)
    print("[uasset_test] Running:", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, env=build_env()).returncode


def parse_cli_json(stdout: str) -> tuple[bool, str, int, str]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return False, "invalid_json", 0, ""

    status_obj = payload.get("status", {})
    if isinstance(status_obj, dict):
        status = str(status_obj.get("status", "unknown"))
    elif isinstance(status_obj, str):
        status = status_obj
    else:
        status = "success" if payload.get("summary") else "unknown"

    diagnostics = payload.get("diagnostics", [])
    diagnostics_count = len(diagnostics) if isinstance(diagnostics, list) else 0
    failure_stage = ""
    if isinstance(diagnostics, list):
        for item in diagnostics:
            if isinstance(item, dict):
                failure_stage = str(item.get("stage") or item.get("module") or item.get("field") or "")
                if failure_stage:
                    break
    return True, status, diagnostics_count, failure_stage


def run_one_compat(asset: Path, timeout: int) -> CompatAssetResult:
    cmd = [
        sys.executable,
        "-m",
        "uasset_read",
        str(asset),
        "--json-summary",
        "--tolerant",
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            cwd=ROOT,
            env=build_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return CompatAssetResult(
            asset_path=str(asset),
            return_code=-1,
            status="timeout",
            valid_json=False,
            diagnostics_count=0,
            failure_stage="",
            elapsed_seconds=time.monotonic() - started,
            error_message=str(exc),
        )

    elapsed = time.monotonic() - started
    valid_json, status, diagnostics_count, failure_stage = parse_cli_json(completed.stdout)
    error = completed.stderr.strip()[:1000]
    if completed.returncode != 0 and valid_json and diagnostics_count == 0:
        status = "failed_without_diagnostics"
    elif completed.returncode != 0 and not status:
        status = "failed"
    return CompatAssetResult(
        asset_path=str(asset),
        return_code=completed.returncode,
        status=status,
        valid_json=valid_json,
        diagnostics_count=diagnostics_count,
        failure_stage=failure_stage,
        elapsed_seconds=elapsed,
        error_message=error,
    )


def summarize_compat(results: list[CompatAssetResult]) -> dict[str, Any]:
    elapsed = [r.elapsed_seconds for r in results if r.status != "timeout"]
    elapsed_sorted = sorted(elapsed)
    if len(elapsed_sorted) >= 2:
        quantiles = statistics.quantiles(elapsed_sorted, n=100)
        p50 = quantiles[49]
        p95 = quantiles[94]
    elif elapsed_sorted:
        p50 = p95 = elapsed_sorted[0]
    else:
        p50 = p95 = 0.0

    failure_stages: dict[str, int] = {}
    for result in results:
        if result.status != "success" and result.failure_stage:
            failure_stages[result.failure_stage] = failure_stages.get(result.failure_stage, 0) + 1

    return {
        "total": len(results),
        "success": sum(1 for r in results if r.status == "success"),
        "partial": sum(1 for r in results if r.status == "partial"),
        "timeout": sum(1 for r in results if r.status == "timeout"),
        "valid_json": sum(1 for r in results if r.valid_json),
        "failed_without_diagnostics": sum(
            1 for r in results
            if r.return_code != 0 and r.status != "timeout" and r.diagnostics_count == 0
        ),
        "elapsed_p50_seconds": round(p50, 3),
        "elapsed_p95_seconds": round(p95, 3),
        "failure_stages": failure_stages,
    }


def run_compat(args: argparse.Namespace) -> int:
    sample_root = resolve_sample_root(args.sample_root)
    if not require_sample_root(sample_root, args.allow_missing_assets):
        return 0 if args.allow_missing_assets else 2

    assets = discover_assets(sample_root)
    if not assets:
        print(f"[uasset_test] No .uasset/.umap files under {sample_root}", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    selected = assets if args.count >= len(assets) else rng.sample(assets, args.count)
    selected = sorted(selected)

    results: list[CompatAssetResult] = []
    for index, asset in enumerate(selected, 1):
        print(f"[uasset_test] compat {index}/{len(selected)} {asset.name}", file=sys.stderr)
        results.append(run_one_compat(asset, args.timeout))

    summary = summarize_compat(results)
    report = {
        "suite": "compat",
        "sample_root": str(sample_root),
        "seed": args.seed,
        "count": len(selected),
        "timeout_seconds": args.timeout,
        "summary": summary,
        "results": [asdict(r) for r in results],
    }

    if args.report_json:
        report_path = Path(args.report_json)
        if not report_path.is_absolute():
            report_path = ROOT / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[uasset_test] Wrote report: {report_path}", file=sys.stderr)
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    if summary["timeout"] or summary["valid_json"] != summary["total"] or summary["failed_without_diagnostics"]:
        return 1
    return 0


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified uasset_read test runner")
    parser.add_argument("suite", choices=sorted([*PYTEST_SUITES.keys(), "compat"]))
    parser.add_argument("--sample-root", default=None)
    parser.add_argument("--allow-missing-assets", action="store_true")
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--report-json", default=None)
    parser.add_argument(
        "--pytest-args",
        nargs=argparse.REMAINDER,
        default=[],
        help="Arguments passed to pytest. Use --pytest-args -- -k pattern",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    if args.suite == "compat":
        return run_compat(args)
    return run_pytest_suite(args)


if __name__ == "__main__":
    raise SystemExit(main())
