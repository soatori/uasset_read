#!/usr/bin/env python3
"""
C++ 输出质量统计脚本 — 扫描生成的 C++ 文件，统计质量指标。

指标说明：
  1. Function_N 占位符比率 — 未解析的函数引用占总函数调用的比例（目标 < 10%）
  2. goto 回退比率 — goto Label_ 回退占总语句行的比例（目标 < 30%）
  3. deprecated token 比率 — 废弃操作符标记数量（仅跟踪）
  4. 空函数体比率 — 空函数体占总函数定义的比例（仅跟踪）

用法：
  python scripts/quality_stats.py path/to/dir
  python scripts/quality_stats.py path/to/dir --json
  python scripts/quality_stats.py path/to/dir --threshold 15
  python scripts/quality_stats.py path/to/dir --verbose
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================================
# 正则模式定义
# ============================================================================

# Function_N 占位符：匹配 Function_\w+\s*\( 或 LocalFunction_\d+\s*\(
RE_FUNCTION_PLACEHOLDER = re.compile(r"(?:Local)?Function_\w+\s*\(")

# 所有函数调用：匹配 标识符\( 模式（排除关键字和控制流）
RE_ALL_FUNCTION_CALLS = re.compile(r"\b(?:\w+::)*\w+\s*\([^)]*\)")

# goto 回退：匹配 goto Label_N
RE_GOTO_FALLBACK = re.compile(r"\bgoto\s+Label_\w+")

# 总语句行：非空、非纯注释、非纯大括号的行
RE_STATEMENT_LINE = re.compile(r"^\s*(?![/{\*])[\w].*;\s*$")

# deprecated token：匹配 /* deprecated */ 或 /* deprecated: ... */
RE_DEPRECATED_TOKEN = re.compile(r"/\*\s*deprecated[^*]*\*/")

# 空函数体：匹配 void FuncName() {} 或其他返回类型的 FuncName() {}
RE_EMPTY_FUNCTION_BODY = re.compile(
    r"(?:void|int|float|bool|auto|FString|FName|FText|UObject\*|"
    r"[A-Z]\w+(?:::\w+)*\*?)\s+"
    r"\w+\s*\([^)]*\)\s*\{\s*\}"
)

# 所有函数定义（含非空体）：匹配 返回类型 [ClassName::]FuncName(...) {
RE_FUNCTION_DEF = re.compile(
    r"(?:void|int|float|bool|auto|FString|FName|FText|UObject\*|"
    r"[A-Z]\w+(?:::\w+)*\*?)\s+"
    r"(?:\w+::)?\w+\s*\([^)]*\)\s*\{"
)

# C++ 源文件扩展名
CPP_EXTENSIONS = {".cpp", ".h", ".hpp", ".cc", ".cxx", ".hxx"}


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class FileStats:
    """单个文件的统计结果。"""
    file_path: str
    total_lines: int = 0
    # Function_N 占位符
    function_placeholder_count: int = 0
    function_call_count: int = 0
    # goto 回退
    goto_fallback_count: int = 0
    statement_line_count: int = 0
    # deprecated token
    deprecated_token_count: int = 0
    # 空函数体
    empty_function_body_count: int = 0
    function_def_count: int = 0


@dataclass
class QualityMetrics:
    """汇总质量指标。"""
    # Function_N 占位符比率
    function_placeholder_count: int = 0
    function_call_count: int = 0
    function_placeholder_ratio: float = 0.0
    function_placeholder_target: float = 0.10  # < 10%
    function_placeholder_pass: Optional[bool] = None

    # goto 回退比率
    goto_fallback_count: int = 0
    statement_line_count: int = 0
    goto_fallback_ratio: float = 0.0
    goto_fallback_target: float = 0.30  # < 30%
    goto_fallback_pass: Optional[bool] = None

    # deprecated token 比率（仅跟踪，无目标）
    deprecated_token_count: int = 0

    # 空函数体比率（仅跟踪，无目标）
    empty_function_body_count: int = 0
    function_def_count: int = 0
    empty_function_body_ratio: float = 0.0

    # 文件统计
    file_count: int = 0
    file_stats: list[FileStats] = field(default_factory=list)


# ============================================================================
# 扫描与统计
# ============================================================================

def scan_file(file_path: Path) -> FileStats:
    """扫描单个 C++ 文件，统计各项指标。"""
    stats = FileStats(file_path=str(file_path))

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return stats

    lines = content.splitlines()
    stats.total_lines = len(lines)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 跳过纯注释行
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # 统计语句行（非空、非纯大括号、非注释、以分号结尾）
        if RE_STATEMENT_LINE.match(line):
            stats.statement_line_count += 1

        # Function_N 占位符
        stats.function_placeholder_count += len(RE_FUNCTION_PLACEHOLDER.findall(line))

        # 所有函数调用（简化计数：匹配 标识符( 模式）
        stats.function_call_count += len(RE_FUNCTION_PLACEHOLDER.findall(line))
        # 计数非占位符的函数调用
        all_calls = len(re.findall(r"\b\w+\s*\(", line))
        # 排除控制流关键字（if, for, while, switch, catch）
        control_flow = len(re.findall(r"\b(?:if|for|while|switch|catch)\s*\(", line))
        stats.function_call_count += max(0, all_calls - control_flow - stats.function_placeholder_count)

        # goto 回退
        stats.goto_fallback_count += len(RE_GOTO_FALLBACK.findall(line))

        # deprecated token
        stats.deprecated_token_count += len(RE_DEPRECATED_TOKEN.findall(line))

        # 函数定义（含空体）
        stats.function_def_count += len(RE_FUNCTION_DEF.findall(line))

        # 空函数体
        stats.empty_function_body_count += len(RE_EMPTY_FUNCTION_BODY.findall(line))

    return stats


def scan_directory(scan_dir: Path, verbose: bool = False) -> QualityMetrics:
    """扫描目录下所有 C++ 文件，汇总质量指标。"""
    metrics = QualityMetrics()

    # 排除的目录（vendor、external、node_modules 等）
    _EXCLUDE_DIRS = {"external", "vendor", "node_modules", ".git", "__pycache__", "third_party"}

    # 收集所有 C++ 源文件（排除 vendor 目录）
    cpp_files = sorted(
        f for f in scan_dir.rglob("*")
        if f.is_file()
        and f.suffix.lower() in CPP_EXTENSIONS
        and not any(part.lower() in _EXCLUDE_DIRS for part in f.relative_to(scan_dir).parts)
    )

    if not cpp_files:
        print(f"警告：在 {scan_dir} 中未找到 C++ 源文件", file=sys.stderr)
        return metrics

    metrics.file_count = len(cpp_files)

    for file_path in cpp_files:
        file_stats = scan_file(file_path)
        metrics.file_stats.append(file_stats)

        # 累加到汇总
        metrics.function_placeholder_count += file_stats.function_placeholder_count
        metrics.function_call_count += file_stats.function_call_count
        metrics.goto_fallback_count += file_stats.goto_fallback_count
        metrics.statement_line_count += file_stats.statement_line_count
        metrics.deprecated_token_count += file_stats.deprecated_token_count
        metrics.empty_function_body_count += file_stats.empty_function_body_count
        metrics.function_def_count += file_stats.function_def_count

    # 计算比率
    if metrics.function_call_count > 0:
        metrics.function_placeholder_ratio = (
            metrics.function_placeholder_count / metrics.function_call_count
        )
    if metrics.statement_line_count > 0:
        metrics.goto_fallback_ratio = (
            metrics.goto_fallback_count / metrics.statement_line_count
        )
    if metrics.function_def_count > 0:
        metrics.empty_function_body_ratio = (
            metrics.empty_function_body_count / metrics.function_def_count
        )

    return metrics


# ============================================================================
# 评估与报告
# ============================================================================

def evaluate_metrics(metrics: QualityMetrics, threshold: Optional[float] = None) -> None:
    """评估指标是否达标。"""
    # Function_N 占位符比率
    if threshold is not None:
        metrics.function_placeholder_target = threshold / 100.0
    metrics.function_placeholder_pass = (
        metrics.function_placeholder_ratio < metrics.function_placeholder_target
    )

    # goto 回退比率
    metrics.goto_fallback_pass = (
        metrics.goto_fallback_ratio < metrics.goto_fallback_target
    )


def format_ratio(value: float) -> str:
    """格式化比率为百分比字符串。"""
    return f"{value * 100:.1f}%"


def format_status(passed: Optional[bool]) -> str:
    """格式化达标状态。"""
    if passed is None:
        return "N/A"
    return "PASS" if passed else "FAIL"


def print_table(metrics: QualityMetrics) -> None:
    """以表格形式输出质量指标。"""
    # 表头
    header = f"{'指标':<30} {'计数':>8} {'总数':>8} {'比率':>8} {'目标':>8} {'状态':>6}"
    separator = "-" * len(header)

    print(separator)
    print("  C++ 输出质量统计报告")
    print(separator)
    print(header)
    print(separator)

    # Function_N 占位符比率
    print(
        f"{'Function_N 占位符比率':<30} "
        f"{metrics.function_placeholder_count:>8} "
        f"{metrics.function_call_count:>8} "
        f"{format_ratio(metrics.function_placeholder_ratio):>8} "
        f"{'< ' + format_ratio(metrics.function_placeholder_target):>8} "
        f"{format_status(metrics.function_placeholder_pass):>6}"
    )

    # goto 回退比率
    print(
        f"{'goto 回退比率':<30} "
        f"{metrics.goto_fallback_count:>8} "
        f"{metrics.statement_line_count:>8} "
        f"{format_ratio(metrics.goto_fallback_ratio):>8} "
        f"{'< ' + format_ratio(metrics.goto_fallback_target):>8} "
        f"{format_status(metrics.goto_fallback_pass):>6}"
    )

    # deprecated token 比率（仅跟踪）
    print(
        f"{'deprecated token':<30} "
        f"{metrics.deprecated_token_count:>8} "
        f"{'---':>8} "
        f"{'---':>8} "
        f"{'仅跟踪':>8} "
        f"{'N/A':>6}"
    )

    # 空函数体比率（仅跟踪）
    print(
        f"{'空函数体比率':<30} "
        f"{metrics.empty_function_body_count:>8} "
        f"{metrics.function_def_count:>8} "
        f"{format_ratio(metrics.empty_function_body_ratio):>8} "
        f"{'仅跟踪':>8} "
        f"{'N/A':>6}"
    )

    print(separator)

    # 汇总信息
    print(f"\n扫描文件数: {metrics.file_count}")

    # 总体评估
    all_pass = all(
        p for p in [
            metrics.function_placeholder_pass,
            metrics.goto_fallback_pass,
        ]
        if p is not None
    )
    status = "全部达标" if all_pass else "存在未达标项"
    print(f"总体评估: {status}")


def print_verbose_details(metrics: QualityMetrics) -> None:
    """输出每个文件的详细统计。"""
    print("\n" + "=" * 80)
    print("  逐文件详细统计")
    print("=" * 80)

    for fs in metrics.file_stats:
        print(f"\n文件: {fs.file_path}")
        print(f"  总行数: {fs.total_lines}")
        print(f"  Function_N 占位符: {fs.function_placeholder_count} / {fs.function_call_count}")
        print(f"  goto 回退: {fs.goto_fallback_count} / {fs.statement_line_count} 语句行")
        print(f"  deprecated token: {fs.deprecated_token_count}")
        print(f"  空函数体: {fs.empty_function_body_count} / {fs.function_def_count}")


def output_json(metrics: QualityMetrics) -> None:
    """以 JSON 格式输出质量指标。"""
    result = {
        "summary": {
            "file_count": metrics.file_count,
            "function_placeholder": {
                "count": metrics.function_placeholder_count,
                "total": metrics.function_call_count,
                "ratio": round(metrics.function_placeholder_ratio, 4),
                "target": metrics.function_placeholder_target,
                "pass": metrics.function_placeholder_pass,
            },
            "goto_fallback": {
                "count": metrics.goto_fallback_count,
                "total": metrics.statement_line_count,
                "ratio": round(metrics.goto_fallback_ratio, 4),
                "target": metrics.goto_fallback_target,
                "pass": metrics.goto_fallback_pass,
            },
            "deprecated_token": {
                "count": metrics.deprecated_token_count,
            },
            "empty_function_body": {
                "count": metrics.empty_function_body_count,
                "total": metrics.function_def_count,
                "ratio": round(metrics.empty_function_body_ratio, 4),
            },
        },
        "files": [
            {
                "path": fs.file_path,
                "total_lines": fs.total_lines,
                "function_placeholder_count": fs.function_placeholder_count,
                "function_call_count": fs.function_call_count,
                "goto_fallback_count": fs.goto_fallback_count,
                "statement_line_count": fs.statement_line_count,
                "deprecated_token_count": fs.deprecated_token_count,
                "empty_function_body_count": fs.empty_function_body_count,
                "function_def_count": fs.function_def_count,
            }
            for fs in metrics.file_stats
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ============================================================================
# CLI 入口
# ============================================================================

def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        description="C++ 输出质量统计 — 扫描生成的 C++ 文件，统计质量指标",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/quality_stats.py output/cpp/\n"
            "  python scripts/quality_stats.py output/cpp/ --json\n"
            "  python scripts/quality_stats.py output/cpp/ --threshold 15\n"
            "  python scripts/quality_stats.py output/cpp/ --verbose\n"
        ),
    )
    parser.add_argument(
        "scan_dir",
        type=Path,
        help="要扫描的目录路径",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 格式输出结果",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="自定义 Function_N 占位符比率阈值（百分比，默认 10）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="输出每个文件的详细统计",
    )

    args = parser.parse_args()

    # 验证目录
    scan_dir: Path = args.scan_dir
    if not scan_dir.is_dir():
        print(f"错误：{scan_dir} 不是有效目录", file=sys.stderr)
        sys.exit(1)

    # 扫描
    metrics = scan_directory(scan_dir, verbose=args.verbose)

    # 零文件检查：无文件可扫描视为 FAIL
    if metrics.file_count == 0:
        print(f"错误：在 {scan_dir} 中未找到 C++ 源文件", file=sys.stderr)
        sys.exit(1)

    # 评估
    evaluate_metrics(metrics, threshold=args.threshold)

    # 输出
    if args.json_output:
        if args.verbose:
            output_json(metrics)
        else:
            output_json(metrics)
    else:
        print_table(metrics)
        if args.verbose:
            print_verbose_details(metrics)

    # 退出码：存在未达标项时返回 1
    has_fail = any(
        p is False for p in [
            metrics.function_placeholder_pass,
            metrics.goto_fallback_pass,
        ]
    )
    sys.exit(1 if has_fail else 0)


if __name__ == "__main__":
    main()
