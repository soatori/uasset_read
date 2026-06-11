#!/usr/bin/env python3
"""源码体积预算检查

检查规则：
- 单文件不超过 1000 行（硬限制）
- 单文件建议不超过 600 行（软限制）
- 总代码行数不超过 35000 行

用法：
    python scripts/quality/size_budget.py [--strict]
"""
import sys
from pathlib import Path


# 体积预算
MAX_FILE_LINES = 1000  # 硬限制
SOFT_LIMIT_LINES = 600  # 软限制（警告）
MAX_TOTAL_LINES = 35000  # 总代码行数预算


def check_file_size(filepath: Path) -> tuple[int, bool]:
    """检查单个文件行数

    Returns:
        (行数, 是否超限)
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = len(f.readlines())
    return lines, lines > MAX_FILE_LINES


def main():
    strict = "--strict" in sys.argv

    src_dir = Path("src/uasset_read")
    if not src_dir.exists():
        print(f"错误: {src_dir} 不存在", file=sys.stderr)
        sys.exit(1)

    # 统计所有 Python 文件
    violations = []
    warnings = []
    total_lines = 0
    file_stats = []

    for py_file in src_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        lines, over_limit = check_file_size(py_file)
        total_lines += lines
        file_stats.append((py_file, lines))

        if over_limit:
            violations.append((py_file, lines))
        elif lines > SOFT_LIMIT_LINES:
            warnings.append((py_file, lines))

    # 输出报告
    print("=" * 70)
    print("源码体积预算报告")
    print("=" * 70)

    print(f"\n总代码行数: {total_lines:,} / {MAX_TOTAL_LINES:,}")
    if total_lines > MAX_TOTAL_LINES:
        print(f"  ❌ 超出预算 {total_lines - MAX_TOTAL_LINES} 行")
    else:
        print(f"  ✅ 剩余预算 {MAX_TOTAL_LINES - total_lines} 行")

    print(f"\n文件数量: {len(file_stats)}")

    if violations:
        print(f"\n❌ 硬限制违规（>{MAX_FILE_LINES} 行）:")
        for filepath, lines in sorted(violations, key=lambda x: -x[1]):
            print(f"  {filepath}: {lines} 行")

    if warnings:
        print(f"\n⚠️  软限制警告（>{SOFT_LIMIT_LINES} 行）:")
        for filepath, lines in sorted(warnings, key=lambda x: -x[1])[:10]:
            print(f"  {filepath}: {lines} 行")

    print("\n" + "=" * 70)

    # 退出码
    if strict and (violations or total_lines > MAX_TOTAL_LINES):
        print("❌ 严格模式：体积预算超标")
        sys.exit(1)
    else:
        print("✅ 体积预算检查通过")
        sys.exit(0)


if __name__ == "__main__":
    main()
