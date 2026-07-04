#!/usr/bin/env python3
"""
解析器输出质量自动检查 — 验证 JSON/Markdown/C++ 输出的数据完整性和解码正确性。

检查项：
  P0: JSON 有效性、raw_data 泄漏、transforms 空、函数无名
  P1: 枚举前缀、MD 缺 Mermaid、MD 缺 IA 绑定表
  P2: name_map 体积、opaque 字段暴露、顶层字段空值

用法：
  python scripts/test_output_quality.py path/to/file.uasset
  python scripts/test_output_quality.py path/to/file.uasset --reference Ref.cpp
  python scripts/test_output_quality.py path/to/file.uasset --quick
  python scripts/test_output_quality.py path/to/file.uasset --output-dir temp/
  python scripts/test_output_quality.py --json-only temp/output.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# 项目根目录（脚本在 scripts/ 下）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUN_PY = PROJECT_ROOT / "run.py"

# ============================================================================
# 检查项定义
# ============================================================================

# P0: raw_data 出现在 FVector/FRotator 类型的 StructProperty 中
RE_RAW_DATA_VECTOR = re.compile(r"raw_data")
# P1: UnknownEnum:: 前缀
RE_UNKNOWN_ENUM = re.compile(r"UnknownEnum::")
# P0: function_name 为 ???
RE_FUNC_UNNAMED = '"???""'


@dataclass
class CheckResult:
    check_id: str
    severity: str  # P0, P1, P2
    name: str
    passed: bool
    detail: str = ""
    hint: str = ""


@dataclass
class QualityReport:
    asset_path: str
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    results: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add(self, result: CheckResult):
        self.total_checks += 1
        if result.passed:
            self.passed += 1
        else:
            self.failed += 1
        self.results.append(result)

    @property
    def pass_rate(self) -> float:
        if self.total_checks == 0:
            return 100.0
        return self.passed / self.total_checks * 100

    def summary_text(self) -> str:
        lines = [
            f"解析器输出质量检查报告",
            f"{'=' * 50}",
            f"资产: {self.asset_path}",
            f"总检查项: {self.total_checks} | 通过: {self.passed} | 失败: {self.failed} | 通过率: {self.pass_rate:.0f}%",
            f"",
        ]

        # 按严重度分组
        for severity in ["P0", "P1", "P2"]:
            group = [r for r in self.results if r.severity == severity]
            if not group:
                continue
            lines.append(f"--- {severity} ---")
            for r in group:
                status = "PASS" if r.passed else "FAIL"
                line = f"  [{status}] {r.name}"
                if r.detail:
                    line += f" — {r.detail}"
                lines.append(line)
            lines.append("")

        # 统计
        if self.stats:
            lines.append("--- 统计 ---")
            for k, v in self.stats.items():
                lines.append(f"  {k}: {v}")
            lines.append("")

        return "\n".join(lines)


# ============================================================================
# 解析器运行
# ============================================================================

def run_parser(uasset_path: Path, output_dir: Path, extra_args: list[str] | None = None) -> dict[str, Path]:
    """运行解析器生成 JSON/MD/C++ 输出，返回输出文件路径映射。"""
    output_files = {}
    formats = [
        ("--json", "json"),
        ("--markdown", "md"),
    ]
    for flag, ext in formats:
        out_path = output_dir / f"{uasset_path.stem}.{ext}"
        cmd = [
            sys.executable, str(RUN_PY),
            str(uasset_path),
            flag,
        ]
        if extra_args:
            cmd.extend(extra_args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(PROJECT_ROOT),
            )
            if result.returncode == 0:
                out_path.write_text(result.stdout, encoding="utf-8")
                output_files[ext] = out_path
            else:
                print(f"  [WARN] {flag} 解析失败 (exit={result.returncode}): {result.stderr[:200]}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print(f"  [WARN] {flag} 解析超时", file=sys.stderr)

    return output_files


# ============================================================================
# JSON 质量检查
# ============================================================================

def check_json_validity(data: dict) -> CheckResult:
    return CheckResult(
        check_id="json_valid",
        severity="P0",
        name="JSON 有效性",
        passed=True,
        detail=f"顶层字段: {len(data)} 个",
    )


def check_summary_fields(data: dict) -> CheckResult:
    summary = data.get("summary", {})
    required = ["package_name", "total_export_count", "total_import_count", "ue_version"]
    missing = [f for f in required if f not in summary]
    return CheckResult(
        check_id="summary_fields",
        severity="P0",
        name="summary 必填字段",
        passed=len(missing) == 0,
        detail=f"缺失: {missing}" if missing else f"{len(summary)} 个字段完整",
    )


def check_raw_data_leak(data: dict) -> CheckResult:
    """检查 exports 中是否有未解码的 raw_data（FVector/FRotator 应被解码）。"""
    raw_count = 0
    total_struct = 0
    for exp in data.get("exports", []):
        for prop in exp.get("properties", []):
            val = prop.get("value", {})
            if isinstance(val, dict) and val.get("type") == "StructProperty":
                total_struct += 1
                if "raw_data" in val:
                    raw_count += 1

    return CheckResult(
        check_id="raw_data_leak",
        severity="P0",
        name="StructProperty raw_data 泄漏",
        passed=raw_count == 0,
        detail=f"{raw_count}/{total_struct} 个 StructProperty 含 raw_data（未解码）",
        hint="FVector/FRotator 等 24 字节结构体应解码为 {X, Y, Z} 或 {Pitch, Yaw, Roll}",
    )


def check_transforms_filled(data: dict) -> CheckResult:
    """检查 blueprint.components[].transforms 是否被填充。"""
    components = data.get("blueprint", {}).get("components", [])
    empty_count = sum(1 for c in components if not c.get("transforms"))

    return CheckResult(
        check_id="transforms_filled",
        severity="P0",
        name="blueprint.components transforms 填充",
        passed=empty_count == 0,
        detail=f"{empty_count}/{len(components)} 个组件 transforms 为空",
        hint="应从 exports StructProperty 解码 RelativeLocation/Rotation/Scale 填充此处",
    )


def check_decompiled_functions_named(data: dict) -> CheckResult:
    """检查 decompiled_functions 的 function_name 是否被正确设置。"""
    funcs = data.get("decompiled_functions", [])
    unnamed = sum(1 for f in funcs if f.get("function_name") in (None, "", "???"))

    return CheckResult(
        check_id="decompiled_named",
        severity="P0",
        name="decompiled_functions 命名",
        passed=unnamed == 0,
        detail=f"{unnamed}/{len(funcs)} 个函数名为空或 '???'",
        hint="应从 blueprint.functions[].name 映射函数名",
    )


def check_enum_prefix(data: dict) -> CheckResult:
    """检查 EnumProperty 值是否含 UnknownEnum:: 前缀。"""
    unknown_count = 0
    total_enum = 0
    for exp in data.get("exports", []):
        for prop in exp.get("properties", []):
            val = prop.get("value", {})
            if isinstance(val, dict) and "enum_type" in val:
                total_enum += 1
                val_name = val.get("value_name", "")
                if val_name.startswith("UnknownEnum::"):
                    unknown_count += 1

    return CheckResult(
        check_id="enum_prefix",
        severity="P1",
        name="EnumProperty UnknownEnum:: 前缀",
        passed=unknown_count == 0,
        detail=f"{unknown_count}/{total_enum} 个枚举值含 UnknownEnum:: 前缀",
        hint="应清洗为 'EFirstPersonPrimitiveType::FirstPerson' 形式",
    )


def check_name_map_size(data: dict) -> CheckResult:
    """检查 name_map 项数占总数据量的比例。"""
    name_map = data.get("name_map", [])
    total_exports = len(data.get("exports", []))
    total_imports = len(data.get("imports", []))
    total_items = total_exports + total_imports + len(name_map)
    name_map_ratio = len(name_map) / max(total_items, 1) * 100

    return CheckResult(
        check_id="name_map_size",
        severity="P2",
        name="name_map 体积占比",
        passed=name_map_ratio < 40,
        detail=f"{len(name_map)} 项，占数据总量 ~{name_map_ratio:.0f}%",
        hint="建议将 name_map 移至 --verbose 模式",
    )


def check_blueprint_components_properties(data: dict) -> CheckResult:
    """检查 blueprint.components 属性是否与 exports 对齐。"""
    bp_comps = {c["name"]: c for c in data.get("blueprint", {}).get("components", [])}
    exports = {e["object_name"]: e for e in data.get("exports", [])}

    mismatches = []
    for name, bp_comp in bp_comps.items():
        bp_props = set(bp_comp.get("properties", {}).keys())
        exp = exports.get(name, {})
        exp_props = set()
        for p in exp.get("properties", []):
            # 排除 raw_data 类属性
            if p.get("type") != "StructProperty" or "raw_data" not in str(p.get("value", {})):
                exp_props.add(p["name"])
        # 允许 bp 有更多（解析后的），但不允许 exp 有但 bp 完全没有的重要属性
        missing_from_bp = exp_props - bp_props - {"AttachParent", "RelativeLocation", "RelativeRotation", "RelativeScale3D"}
        if missing_from_bp and len(missing_from_bp) > 2:
            mismatches.append(f"{name}: 缺 {missing_from_bp}")

    return CheckResult(
        check_id="bp_comp_props",
        severity="P1",
        name="blueprint.components 属性对齐",
        passed=len(mismatches) == 0,
        detail=f"{len(mismatches)} 个组件属性未对齐" if mismatches else "属性对齐",
    )


def check_top_level_empty_fields(data: dict) -> CheckResult:
    """检查顶层字段是否为空。"""
    empty_fields = []
    for key in ["soft_object_paths", "soft_package_references"]:
        val = data.get(key)
        if val is not None and (isinstance(val, (list, dict)) and len(val) == 0):
            empty_fields.append(key)

    return CheckResult(
        check_id="top_level_empty",
        severity="P2",
        name="顶层空字段",
        passed=len(empty_fields) == 0,
        detail=f"空字段: {empty_fields}" if empty_fields else "无空字段",
    )


def check_output_version_semantic(data: dict) -> CheckResult:
    """检查 output_version 字段语义。"""
    ov = data.get("output_version", "")
    return CheckResult(
        check_id="output_version",
        severity="P2",
        name="output_version 语义",
        passed=bool(ov),
        detail=f'值: "{ov}"（需确认是解析器版本还是输出格式版本）',
    )


# ============================================================================
# Markdown 质量检查
# ============================================================================

def check_md_mermaid(md_content: str) -> CheckResult:
    """检查 Markdown 是否包含组件层级 Mermaid 图。"""
    has_mermaid = "```mermaid" in md_content or "graph TD" in md_content
    return CheckResult(
        check_id="md_mermaid",
        severity="P1",
        name="Markdown 组件层级 Mermaid 图",
        passed=has_mermaid,
        detail="包含 Mermaid 图" if has_mermaid else "缺少组件层级可视化图",
        hint="应添加 graph TD 展示 SCS 组件层级关系",
    )


def check_md_input_binding_table(md_content: str) -> CheckResult:
    """检查 Markdown 是否包含 Input Action 绑定表。"""
    has_table = "IA_Move" in md_content and "Triggered" in md_content
    # 更精确：查找 IA_ 相关的表格行
    has_ia_table = bool(re.search(r"\|\s*IA_\w+\s*\|", md_content))
    return CheckResult(
        check_id="md_ia_table",
        severity="P1",
        name="Markdown Input Action 绑定表",
        passed=has_ia_table,
        detail="包含 IA 绑定表" if has_ia_table else "缺少 Input Action 绑定关系表",
        hint="应添加表格展示 IA_Move/IA_Look/IA_MouseLook/IA_Jump 的触发绑定",
    )


def check_md_variable_dump(md_content: str) -> CheckResult:
    """检查 Markdown Variables 表是否含 raw struct dump。"""
    has_dump = "StructValue(struct_type=" in md_content
    return CheckResult(
        check_id="md_var_dump",
        severity="P2",
        name="Markdown Variables raw struct dump",
        passed=not has_dump,
        detail="含 raw dump" if has_dump else "已清洗",
        hint="opaque 结构体应只显示 struct_type + parse_status",
    )


# ============================================================================
# 参考 C++ 对照（可选）
# ============================================================================

def check_reference_cpp(reference_path: Path, data: dict) -> list[CheckResult]:
    """对照参考 C++ 代码，检查解析器输出的组件/函数覆盖。"""
    results = []
    if not reference_path.exists():
        return [CheckResult("ref_exists", "P0", "参考 C++ 文件存在", passed=False, detail=f"文件不存在: {reference_path}")]

    cpp_content = reference_path.read_text(encoding="utf-8")

    # 提取 C++ 中的 UPROPERTY 组件名
    cpp_components = set(re.findall(r'U[A-Za-z]*Component\*\s+(\w+)', cpp_content))
    # 提取 C++ 中的函数定义（匹配 ClassName::FuncName(...) { 模式）
    cpp_functions = set(re.findall(r'(?:\w+::)?(\w+)\s*\([^)]*\)\s*\{', cpp_content))
    # 排除控制流和非游戏函数
    cpp_functions -= {"if", "while", "for", "switch", "catch", "return", "AFirstPersonCCharacter", "ABP_FirstPersonCharacter"}

    # 提取蓝图中的组件名
    bp_components = {c["name"] for c in data.get("blueprint", {}).get("components", [])}
    # 提取蓝图中的函数名
    bp_functions = {f["name"] for f in data.get("blueprint", {}).get("functions", [])}

    # 组件覆盖
    bp_only = bp_components - cpp_components
    cpp_only = cpp_components - bp_components

    results.append(CheckResult(
        check_id="ref_components",
        severity="P1",
        name="参考 C++ vs 蓝图组件覆盖",
        passed=True,  # 差异是正常的（C++ 通常简化）
        detail=f"蓝图独有: {bp_only or '无'} | C++独有: {cpp_only or '无'}",
        hint="C++ 通常复用基类内置组件，只创建蓝图新增组件",
    ))

    # 函数覆盖
    bp_func_only = bp_functions - cpp_functions
    cpp_func_only = cpp_functions - bp_functions

    results.append(CheckResult(
        check_id="ref_functions",
        severity="P1",
        name="参考 C++ vs 蓝图函数覆盖",
        passed=True,
        detail=f"蓝图独有: {bp_func_only or '无'} | C++独有: {cpp_func_only or '无'}",
        hint="C++ 可能合并或重命名蓝图函数",
    ))

    return results


# ============================================================================
# 主检查流程
# ============================================================================

ALL_JSON_CHECKS = [
    check_json_validity,
    check_summary_fields,
    check_raw_data_leak,
    check_transforms_filled,
    check_decompiled_functions_named,
    check_enum_prefix,
    check_name_map_size,
    check_blueprint_components_properties,
    check_top_level_empty_fields,
    check_output_version_semantic,
]

ALL_MD_CHECKS = [
    check_md_mermaid,
    check_md_input_binding_table,
    check_md_variable_dump,
]


def run_quality_check(
    uasset_path: Path,
    output_dir: Path,
    reference_path: Optional[Path] = None,
    quick: bool = False,
) -> QualityReport:
    """运行完整质量检查流程。"""
    report = QualityReport(asset_path=str(uasset_path))

    # Step 1: 运行解析器
    print(f"正在解析: {uasset_path.name}")
    output_files = run_parser(uasset_path, output_dir)

    if not output_files:
        report.add(CheckResult("parse", "P0", "解析器执行", passed=False, detail="所有格式解析失败"))
        return report

    # Step 2: JSON 检查
    data = None
    json_path = output_files.get("json")
    if json_path and json_path.exists():
        print(f"  检查 JSON: {json_path.name}")
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            report.add(CheckResult("json_parse", "P0", "JSON 解析", passed=False, detail=str(e)))
            return report

        # 运行所有 JSON 检查
        for check_fn in ALL_JSON_CHECKS:
            result = check_fn(data)
            report.add(result)

        # 收集统计
        report.stats["JSON 行数"] = sum(1 for _ in open(json_path, encoding="utf-8"))
        report.stats["exports"] = len(data.get("exports", []))
        report.stats["imports"] = len(data.get("imports", []))
        report.stats["blueprint.components"] = len(data.get("blueprint", {}).get("components", []))
        report.stats["decompiled_functions"] = len(data.get("decompiled_functions", []))
    else:
        report.add(CheckResult("json_gen", "P0", "JSON 生成", passed=False, detail="JSON 输出文件未生成"))

    # Step 3: Markdown 检查
    if not quick:
        md_path = output_files.get("md")
        if md_path and md_path.exists():
            print(f"  检查 Markdown: {md_path.name}")
            md_content = md_path.read_text(encoding="utf-8")
            for check_fn in ALL_MD_CHECKS:
                result = check_fn(md_content)
                report.add(result)
            report.stats["Markdown 行数"] = md_content.count("\n") + 1
        else:
            report.add(CheckResult("md_gen", "P1", "Markdown 生成", passed=False, detail="Markdown 输出文件未生成"))

    # Step 4: 参考 C++ 对照
    if reference_path and data is not None:
        print(f"  对照参考 C++: {reference_path.name}")
        ref_results = check_reference_cpp(reference_path, data)
        for r in ref_results:
            report.add(r)

    return report


def main():
    parser = argparse.ArgumentParser(
        description="解析器输出质量自动检查",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python scripts/test_output_quality.py path/to/file.uasset
  python scripts/test_output_quality.py path/to/file.uasset --reference Ref.cpp
  python scripts/test_output_quality.py path/to/file.uasset --quick
  python scripts/test_output_quality.py --json-only temp/output.json
        """,
    )
    parser.add_argument("uasset", nargs="?", type=Path, help="目标 .uasset 文件路径")
    parser.add_argument("--reference", type=Path, help="参考 C++ 代码路径（可选对照）")
    parser.add_argument("--quick", action="store_true", help="快速模式：仅 JSON 检查，跳过 Markdown")
    parser.add_argument("--output-dir", type=Path, default=None, help="输出目录（默认 temp/）")
    parser.add_argument("--json-only", type=Path, help="仅检查已有 JSON 文件，不运行解析器")

    args = parser.parse_args()

    # 仅 JSON 模式
    if args.json_only:
        print(f"检查 JSON: {args.json_only}")
        with open(args.json_only, encoding="utf-8") as f:
            data = json.load(f)
        report = QualityReport(asset_path=str(args.json_only))
        for check_fn in ALL_JSON_CHECKS:
            report.add(check_fn(data))
        report.stats["JSON 行数"] = sum(1 for _ in open(args.json_only, encoding="utf-8"))
        print(report.summary_text())
        sys.exit(0 if report.failed == 0 else 1)

    # 完整模式
    if not args.uasset:
        parser.error("需要提供 .uasset 文件路径（或使用 --json-only）")

    output_dir = args.output_dir or PROJECT_ROOT / "temp"
    output_dir.mkdir(parents=True, exist_ok=True)

    report = run_quality_check(args.uasset, output_dir, args.reference, args.quick)

    print()
    print(report.summary_text())

    # 保存报告
    report_path = output_dir / f"{args.uasset.stem}-quality-report.md"
    report_path.write_text(
        f"# 解析器输出质量检查报告\n\n资产: {args.uasset}\n\n{report.summary_text()}\n",
        encoding="utf-8",
    )
    print(f"报告已保存: {report_path}")

    sys.exit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
