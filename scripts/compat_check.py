"""固定种子兼容性抽测脚本 — 验证广谱 .uasset 资产的 CLI 解析质量。

用法:
    python scripts/compat_check.py                          # 默认 24 个样本
    python scripts/compat_check.py --count 48               # 自定义样本数
    python scripts/compat_check.py --seed 123               # 自定义种子
    python scripts/compat_check.py --sample-root /path/to   # 自定义样本根目录
    python scripts/compat_check.py --output report.json     # 输出到文件

验收标准（v1）:
    - --json-summary --tolerant 全部返回合法 JSON
    - 无 subprocess timeout
    - 失败样本包含 diagnostics 和明确 stage
    - 记录性能指标：单资产耗时、P50、P95、超时数量
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


DEFAULT_SAMPLE_ROOT = r"E:\Develop\lib\UnrealEngine\Samples"
DEFAULT_COUNT = 24
DEFAULT_SEED = 42
TIMEOUT_SECONDS = 60


@dataclass
class AssetReport:
    """单个资产的检测报告。"""
    asset_path: str
    asset_name: str
    return_code: int
    status: str = ""  # "success" / "failed" / "timeout" / "invalid_json" / "subprocess_error"
    is_valid_json: bool = False
    diagnostics_count: int = 0
    failure_stage: str = ""  # 从 diagnostics 中提取
    elapsed_seconds: float = 0.0
    error_message: str = ""


@dataclass
class CompatReport:
    """兼容性抽测总报告。"""
    timestamp: str = ""
    sample_root: str = ""
    seed: int = 0
    count: int = 0
    timeout_seconds: int = TIMEOUT_SECONDS
    results: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def discover_assets(sample_root: str) -> list[str]:
    """发现所有 .uasset 文件。"""
    assets = []
    for dirpath, _, filenames in os.walk(sample_root):
        for f in filenames:
            if f.endswith(".uasset"):
                assets.append(os.path.join(dirpath, f))
    return sorted(assets)


def select_assets(all_assets: list[str], count: int, seed: int) -> list[str]:
    """使用固定种子选择样本资产。"""
    rng = random.Random(seed)
    if count >= len(all_assets):
        return all_assets
    return rng.sample(all_assets, count)


def run_single_check(asset_path: str, timeout: int) -> AssetReport:
    """对单个资产执行 CLI 兼容性检测。"""
    report = AssetReport(
        asset_path=asset_path,
        asset_name=os.path.basename(asset_path),
        return_code=-1,
    )

    cmd = [
        sys.executable, "-m", "uasset_read",
        "--json-summary", "--tolerant",
        asset_path,
    ]

    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/..",
        )
        report.elapsed_seconds = time.monotonic() - start
        report.return_code = result.returncode

        if result.returncode != 0:
            report.status = "failed"
            report.error_message = result.stderr[:500] if result.stderr else ""
            # 尝试从 stdout 解析 JSON（tolerant 模式可能仍输出 JSON）
            _try_parse_output(result.stdout, report)
            return report

        # 尝试解析 JSON 输出
        _try_parse_output(result.stdout, report)

    except subprocess.TimeoutExpired:
        report.elapsed_seconds = time.monotonic() - start
        report.status = "timeout"
        report.error_message = f"Timeout after {timeout}s"
    except Exception as e:
        report.elapsed_seconds = time.monotonic() - start
        report.status = "subprocess_error"
        report.error_message = str(e)

    return report


def _try_parse_output(stdout: str, report: AssetReport) -> None:
    """尝试解析 CLI stdout 为 JSON，提取 status 和 diagnostics。"""
    if not stdout.strip():
        if not report.status:
            report.status = "empty_output"
        return

    try:
        data = json.loads(stdout)
        report.is_valid_json = True

        # 提取 status
        status_obj = data.get("status", {})
        if isinstance(status_obj, dict):
            report.status = status_obj.get("status", "unknown")
        elif isinstance(status_obj, str):
            report.status = status_obj
        else:
            report.status = "success" if data.get("summary") else "unknown"

        # 提取 diagnostics
        diagnostics = data.get("diagnostics", [])
        if isinstance(diagnostics, list):
            report.diagnostics_count = len(diagnostics)
            # 提取第一个失败阶段
            for d in diagnostics:
                if isinstance(d, dict) and d.get("kind") == "parse_stage_error":
                    report.failure_stage = d.get("module", "unknown")
                    break
                elif isinstance(d, dict) and d.get("module"):
                    report.failure_stage = d["module"]
                    break

    except json.JSONDecodeError:
        report.is_valid_json = False
        if not report.status:
            report.status = "invalid_json"


def compute_percentile(values: list[float], p: float) -> float:
    """计算百分位数。"""
    if not values:
        return 0.0
    return statistics.quantiles(values, n=100)[int(p) - 1] if len(values) >= 2 else values[0]


def build_summary(results: list[AssetReport]) -> dict:
    """构建汇总统计。"""
    total = len(results)
    success = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "failed")
    timeout = sum(1 for r in results if r.status == "timeout")
    invalid_json = sum(1 for r in results if r.status == "invalid_json")
    valid_json = sum(1 for r in results if r.is_valid_json)

    times = [r.elapsed_seconds for r in results if r.status != "timeout"]
    times_sorted = sorted(times)

    p50 = 0.0
    p95 = 0.0
    if times_sorted:
        if len(times_sorted) >= 2:
            quantiles = statistics.quantiles(times_sorted, n=100)
            p50 = quantiles[49]
            p95 = quantiles[94]
        else:
            p50 = times_sorted[0]
            p95 = times_sorted[0]

    # 失败样本的阶段分布（仅统计非成功状态）
    failure_stages: dict[str, int] = {}
    for r in results:
        if r.failure_stage and r.status not in ("success",):
            failure_stages[r.failure_stage] = failure_stages.get(r.failure_stage, 0) + 1

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "timeout": timeout,
        "invalid_json": invalid_json,
        "valid_json_count": valid_json,
        "valid_json_rate": f"{valid_json / total * 100:.1f}%" if total else "N/A",
        "success_rate": f"{success / total * 100:.1f}%" if total else "N/A",
        "elapsed_p50_seconds": round(p50, 3),
        "elapsed_p95_seconds": round(p95, 3),
        "elapsed_mean_seconds": round(statistics.mean(times), 3) if times else 0,
        "elapsed_max_seconds": round(max(times), 3) if times else 0,
        "failure_stages": failure_stages,
    }


def main():
    parser = argparse.ArgumentParser(description="固定种子兼容性抽测")
    parser.add_argument("--sample-root", default=DEFAULT_SAMPLE_ROOT,
                        help="样本资产根目录")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT,
                        help="抽样数量（默认 24）")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="随机种子（默认 42）")
    parser.add_argument("--timeout", type=int, default=TIMEOUT_SECONDS,
                        help="单资产超时秒数（默认 60）")
    parser.add_argument("--output", type=str, default=None,
                        help="输出 JSON 报告文件路径")
    args = parser.parse_args()

    # 发现资产
    print(f"发现资产目录: {args.sample_root}", file=sys.stderr)
    all_assets = discover_assets(args.sample_root)
    print(f"发现 .uasset 文件: {len(all_assets)}", file=sys.stderr)

    if not all_assets:
        print("错误: 未发现任何 .uasset 文件", file=sys.stderr)
        sys.exit(1)

    # 选择样本
    selected = select_assets(all_assets, args.count, args.seed)
    print(f"选取样本: {len(selected)}（seed={args.seed}）", file=sys.stderr)

    # 执行检测
    results: list[AssetReport] = []
    for i, asset in enumerate(selected, 1):
        name = os.path.basename(asset)
        print(f"[{i}/{len(selected)}] {name}...", file=sys.stderr, end=" ", flush=True)
        report = run_single_check(asset, args.timeout)
        results.append(report)
        status_icon = {
            "success": "✓",
            "failed": "✗",
            "timeout": "⏱",
            "invalid_json": "⚠",
            "empty_output": "∅",
        }.get(report.status, "?")
        print(f"{status_icon} {report.status} ({report.elapsed_seconds:.1f}s, diag={report.diagnostics_count})", file=sys.stderr)

    # 构建报告
    summary = build_summary(results)
    report_obj = CompatReport(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        sample_root=args.sample_root,
        seed=args.seed,
        count=len(selected),
        timeout_seconds=args.timeout,
        results=[asdict(r) for r in results],
        summary=summary,
    )

    # 输出
    report_json = json.dumps(asdict(report_obj), indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(report_json, encoding="utf-8")
        print(f"\n报告已写入: {args.output}", file=sys.stderr)
    else:
        print(report_json)

    # 打印摘要
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"兼容性抽测摘要", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"  总计: {summary['total']}", file=sys.stderr)
    print(f"  成功: {summary['success']} ({summary['success_rate']})", file=sys.stderr)
    print(f"  失败: {summary['failed']}", file=sys.stderr)
    print(f"  超时: {summary['timeout']}", file=sys.stderr)
    print(f"  合法 JSON: {summary['valid_json_count']} ({summary['valid_json_rate']})", file=sys.stderr)
    print(f"  耗时 P50: {summary['elapsed_p50_seconds']}s", file=sys.stderr)
    print(f"  耗时 P95: {summary['elapsed_p95_seconds']}s", file=sys.stderr)
    if summary['failure_stages']:
        print(f"  失败阶段分布: {summary['failure_stages']}", file=sys.stderr)

    # 验收检查
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"验收检查", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    checks = []
    if summary['timeout'] > 0:
        checks.append(f"✗ 存在 {summary['timeout']} 个超时样本")
    else:
        checks.append("✓ 无超时")

    if summary['valid_json_count'] == summary['total']:
        checks.append("✓ 全部返回合法 JSON")
    else:
        checks.append(f"✗ {summary['total'] - summary['valid_json_count']} 个样本返回非法 JSON")

    # 检查失败样本是否有 diagnostics
    failed_without_diag = [
        r for r in results
        if r.status in ("failed", "invalid_json") and r.diagnostics_count == 0
    ]
    if failed_without_diag:
        checks.append(f"✗ {len(failed_without_diag)} 个失败样本缺少 diagnostics")
    else:
        checks.append("✓ 失败样本均包含 diagnostics")

    for c in checks:
        print(f"  {c}", file=sys.stderr)

    # 如果有超时或非法 JSON，退出码为 1
    if summary['timeout'] > 0 or summary['valid_json_count'] < summary['total']:
        sys.exit(1)


if __name__ == "__main__":
    main()
