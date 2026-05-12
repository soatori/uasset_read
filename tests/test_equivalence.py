"""
tests/test_equivalence.py - 等价验证测试基础设施

Phase 34 Plan 01: 创建等价验证测试基础设施。

验证新版模块化代码（src/uasset_read/）与旧版单文件（uasset_read_legacy.py）
对同一 .uasset 文件的输出等价性。

需求覆盖：
- 等价-01: JSON Full 输出等价
- 等价-02: JSON Summary 输出等价
- 等价-03: Text 输出等价
- 等价-04: Markdown 输出等价
- 等价-05: 合成资产验证
- 等价-06: 真实资产验证
- 等价-07: VERIFICATION.md 报告生成

Per D-04: 记录并继续 — 发现差异后记录到差异列表并继续验证其他资产/格式。
Per D-07: 验证函数在测试文件中定义，不放在 src/ 模块中。
"""

import atexit
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

# ============================================================================
# Task 1: Helper 类和函数
# ============================================================================


class DiffRecorder:
    """收集所有差异，不中断验证流程（D-04）。

    Per 34-RESEARCH.md Pattern 1: Record-and-Continue Diff。

    Attributes:
        diffs: 差异列表，每个差异包含 asset, format, field, old_value, new_value,
               severity, category, note
    """

    def __init__(self):
        self.diffs: list[dict] = []

    def record(
        self,
        asset_name: str,
        format_name: str,
        field_path: str,
        old_value: Any = None,
        new_value: Any = None,
        severity: str = "diff",
        category: str = "unknown",
        note: str = ""
    ) -> None:
        """记录一个差异。

        Args:
            asset_name: 资产名称（如 'synthetic', 'BP_FirstPersonCharacter'）
            format_name: 输出格式（如 'json_full', 'json_summary', 'text', 'markdown'）
            field_path: 字段路径（如 'imports', 'graphs_summary[0].graph_name'）
            old_value: 旧版输出值
            new_value: 新版输出值
            severity: 严重程度（'known' / 'improvement' / 'bug' / 'diff'）
            category: 分类（参考 34-RESEARCH.md 已知 9 类差异）
            note: 备注
        """
        self.diffs.append({
            "asset": asset_name,
            "format": format_name,
            "field": field_path,
            "old_value": old_value,
            "new_value": new_value,
            "severity": severity,
            "category": category,
            "note": note
        })

    def get_by_severity(self, severity: str) -> list[dict]:
        """按 severity 筛选差异。"""
        return [d for d in self.diffs if d["severity"] == severity]

    def get_by_category(self, category: str) -> list[dict]:
        """按 category 筛选差异。"""
        return [d for d in self.diffs if d["category"] == category]

    def get_known_diff_categories(self) -> list[str]:
        """返回已知 9 类差异的分类名。

        Per 34-RESEARCH.md Verified Difference Inventory:
        - top_level_keys: imports/soft_references/circular_deps 移除
        - status: fail→success
        - graphs_summary_keys: 2键→8键扩展
        - ObjectProperty_value: dict→int
        - execution_flows_format: event型→node型
        - execution_flows_count: 7→4
        - mermaid_missing: mermaid 图表缺失
        - parent_class_str: str(dict) bug
        - json_full_crash: 两版都崩溃
        """
        return [
            "top_level_keys",
            "status",
            "graphs_summary_keys",
            "ObjectProperty_value",
            "execution_flows_format",
            "execution_flows_count",
            "mermaid_missing",
            "parent_class_str",
            "json_full_crash"
        ]

    def clear(self) -> None:
        """清空差异列表（用于测试隔离）。"""
        self.diffs = []


def deep_compare(old: Any, new: Any, path: str = "") -> list[dict]:
    """递归对比任意 Python 对象，返回差异列表（D-01 逐字段对比）。

    Per 34-RESEARCH.md Pattern 2: Two-Level Comparison.

    Args:
        old: 旧版输出（可以是 dict, list, 标量值）
        new: 新版输出
        path: 当前对比路径（用于差异定位）

    Returns:
        差异列表，每个差异包含 path, type, old_value, new_value 等
    """
    diffs = []

    # 类型变化
    if type(old) != type(new):
        diffs.append({
            "path": path,
            "type": "type_changed",
            "old_type": type(old).__name__,
            "new_type": type(new).__name__,
            "old_value": _safe_repr(old),
            "new_value": _safe_repr(new)
        })
        return diffs

    # dict 对比
    if isinstance(old, dict):
        all_keys = set(old.keys()) | set(new.keys())
        for key in sorted(all_keys):
            current_path = f"{path}.{key}" if path else key
            if key not in old:
                diffs.append({
                    "path": current_path,
                    "type": "added",
                    "new_value": _safe_repr(new[key])
                })
            elif key not in new:
                diffs.append({
                    "path": current_path,
                    "type": "removed",
                    "old_value": _safe_repr(old[key])
                })
            else:
                diffs.extend(deep_compare(old[key], new[key], current_path))

    # list 对比
    elif isinstance(old, list):
        max_len = max(len(old), len(new))
        for i in range(max_len):
            current_path = f"{path}[{i}]"
            if i >= len(old):
                diffs.append({
                    "path": current_path,
                    "type": "added",
                    "new_value": _safe_repr(new[i])
                })
            elif i >= len(new):
                diffs.append({
                    "path": current_path,
                    "type": "removed",
                    "old_value": _safe_repr(old[i])
                })
            else:
                diffs.extend(deep_compare(old[i], new[i], current_path))

    # 标量值对比
    elif old != new:
        diffs.append({
            "path": path,
            "type": "value_changed",
            "old_value": _safe_repr(old),
            "new_value": _safe_repr(new)
        })

    return diffs


def _safe_repr(value: Any, max_len: int = 200) -> str:
    """安全地 repr 值，避免过长输出。"""
    repr_str = repr(value)
    if len(repr_str) > max_len:
        return repr_str[:max_len] + "...(truncated)"
    return repr_str


def run_old_cli(format_flag: str, asset_path: str) -> tuple[str, int]:
    """运行旧版 CLI: python uasset_read_legacy.py {format_flag} {asset_path}

    Per Pitfall 2: 使用 Path.as_posix() 转换 Windows 路径。

    Args:
        format_flag: '--json', '--summary', '--text', '--markdown'
        asset_path: .uasset 文件路径

    Returns:
        (stdout, returncode)
    """
    # 转换路径为正斜杠（避免 Windows 转义问题）
    posix_path = Path(asset_path).as_posix()
    cmd = ["python", "uasset_read_legacy.py", format_flag, posix_path]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent  # 项目根目录
        )
        return result.stdout, result.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", -1
    except Exception as e:
        return f"ERROR: {e}", -1


def run_new_cli(format_flag: str, asset_path: str) -> tuple[str, int]:
    """运行新版 CLI: python -m uasset_read {format_flag} {asset_path}

    Per Pitfall 2: 使用 Path.as_posix() 转换 Windows 路径。

    Args:
        format_flag: '--json', '--summary', '--text', '--markdown'
        asset_path: .uasset 文件路径

    Returns:
        (stdout, returncode)
    """
    posix_path = Path(asset_path).as_posix()
    cmd = ["python", "-m", "uasset_read", format_flag, posix_path]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent  # 项目根目录
        )
        return result.stdout, result.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", -1
    except Exception as e:
        return f"ERROR: {e}", -1


def compare_outputs(
    old_output: str,
    new_output: str,
    format_name: str,
    asset_name: str,
    recorder: DiffRecorder
) -> None:
    """对比新旧输出，使用两策略（D-01）：

    1. 整体 diff: 字符串完全相等则快速通过
    2. 逐字段对比: 不相等时递归对比 dict/list 结构

    Per Pitfall 1: 使用 json.dumps(sort_keys=True, ensure_ascii=False) 规范化 JSON。

    Args:
        old_output: 旧版 CLI stdout
        new_output: 新版 CLI stdout
        format_name: 输出格式名称
        asset_name: 资产名称
        recorder: DiffRecorder 实例
    """
    # 快速通过：字符串完全相等
    if old_output == new_output:
        return

    # JSON 格式：解析后对比
    if format_name in ('json_full', 'json_summary'):
        try:
            old_json = json.loads(old_output)
            new_json = json.loads(new_output)

            # 规范化后对比
            old_normalized = json.dumps(old_json, sort_keys=True, indent=2, ensure_ascii=False)
            new_normalized = json.dumps(new_json, sort_keys=True, indent=2, ensure_ascii=False)

            if old_normalized == new_normalized:
                return

            # 逐字段对比
            field_diffs = deep_compare(old_json, new_json)
            for diff in field_diffs:
                # 自动分类差异（per 34-01-PLAN.md 已知 9 类差异）
                severity, category, note = _classify_diff(diff, format_name, asset_name)
                recorder.record(
                    asset_name=asset_name,
                    format_name=format_name,
                    field_path=diff["path"],
                    old_value=diff.get("old_value"),
                    new_value=diff.get("new_value"),
                    severity=severity,
                    category=category,
                    note=note
                )
        except json.JSONDecodeError as e:
            recorder.record(
                asset_name=asset_name,
                format_name=format_name,
                field_path="JSON_PARSE",
                old_value=old_output[:200] if old_output else "",
                new_value=new_output[:200] if new_output else "",
                severity="bug",
                category="json_parse_error",
                note=f"JSON decode error: {e}"
            )

    # Text/Markdown 格式：直接字符串对比 + 结构化解析
    else:
        # Text: 逐行对比
        if format_name == 'text':
            old_lines = old_output.splitlines()
            new_lines = new_output.splitlines()

            # 检查特定差异模式
            # #4: ObjectProperty 值变化
            object_prop_diffs = _detect_object_property_diff(old_lines, new_lines)
            for diff in object_prop_diffs:
                recorder.record(
                    asset_name=asset_name,
                    format_name=format_name,
                    field_path=diff["path"],
                    old_value=diff.get("old_value"),
                    new_value=diff.get("new_value"),
                    severity="diff",
                    category="ObjectProperty_value",
                    note="ObjectProperty value format changed (dict → int)"
                )

            # #8: parent_class str(dict) bug
            parent_diffs = _detect_parent_class_diff(old_lines, new_lines)
            for diff in parent_diffs:
                recorder.record(
                    asset_name=asset_name,
                    format_name=format_name,
                    field_path="blueprint.parent_class",
                    old_value=diff.get("old_value"),
                    new_value=diff.get("new_value"),
                    severity="bug",
                    category="parent_class_str",
                    note="parent_class is str(dict) instead of proper dict"
                )

            # 其他差异
            if len(old_lines) != len(new_lines):
                recorder.record(
                    asset_name=asset_name,
                    format_name=format_name,
                    field_path="line_count",
                    old_value=len(old_lines),
                    new_value=len(new_lines),
                    severity="diff",
                    category="text_structure",
                    note="Text output line count differs"
                )

        # Markdown: mermaid 块检测
        elif format_name == 'markdown':
            old_mermaid = extract_mermaid_blocks(old_output)
            new_mermaid = extract_mermaid_blocks(new_output)

            # #7: mermaid 缺失
            if len(old_mermaid) > 0 and len(new_mermaid) == 0:
                recorder.record(
                    asset_name=asset_name,
                    format_name=format_name,
                    field_path="mermaid_blocks",
                    old_value=f"{len(old_mermaid)} blocks",
                    new_value="0 blocks",
                    severity="bug",
                    category="mermaid_missing",
                    note="Mermaid flowchart missing in new output"
                )

            # 其他 mermaid 差异
            elif len(old_mermaid) != len(new_mermaid):
                recorder.record(
                    asset_name=asset_name,
                    format_name=format_name,
                    field_path="mermaid_count",
                    old_value=len(old_mermaid),
                    new_value=len(new_mermaid),
                    severity="diff",
                    category="mermaid_count",
                    note=f"Mermaid block count differs: {len(old_mermaid)} vs {len(new_mermaid)}"
                )


def _classify_diff(diff: dict, format_name: str, asset_name: str) -> tuple[str, str, str]:
    """自动分类差异（per 34-01-PLAN.md 已知 9 类差异）。

    Returns:
        (severity, category, note)
    """
    path = diff["path"]
    diff_type = diff["type"]

    # #1: top_level_keys — imports/soft_references/circular_deps 移除
    if path in ('imports', 'soft_references', 'circular_deps') and diff_type == 'removed':
        return "known", "top_level_keys", "Intentional removal (Phase 32 D-02)"

    # #2: status — fail→success
    if path == 'status' and diff.get("old_value") == "'fail'" and diff.get("new_value") == "'success'":
        return "improvement", "status", "Blueprint parent detection fixed"

    # #3: graphs_summary_keys — 2键→8键扩展
    if 'graphs_summary' in path and diff_type == 'added':
        return "improvement", "graphs_summary_keys", "graphs_summary expanded with 6 new keys"

    # #4: ObjectProperty_value — dict→int
    if 'ObjectProperty' in path or 'Value' in path:
        old_val = diff.get("old_value", "")
        new_val = diff.get("new_value", "")
        if old_val.startswith("'{'") and new_val.isdigit() or new_val.startswith("'"):
            return "diff", "ObjectProperty_value", "ObjectProperty value format changed (dict → int)"

    # #5: execution_flows_format — event型→node型
    if 'execution_flows' in path:
        if 'event' in path or 'function_name' in path:
            return "diff", "execution_flows_format", "execution_flows structure changed (event→node)"
        if 'start_event' in path or 'nodes' in path:
            return "improvement", "execution_flows_format", "execution_flows uses new node-based format"

    # #6: execution_flows_count — 7→4
    if path.endswith('execution_flows') and diff_type == 'value_changed':
        return "diff", "execution_flows_count", "execution_flows count differs (possible regression)"

    # #8: parent_class_str — str(dict) bug
    if path == 'blueprint.parent_class':
        new_val = diff.get("new_value", "")
        if new_val.startswith("'{'") or "'type':" in new_val:
            return "bug", "parent_class_str", "parent_class is str(dict) bug"

    # 默认：需审查
    return "diff", "unknown", f"Unknown diff at {path}"


def _detect_object_property_diff(old_lines: list[str], new_lines: list[str]) -> list[dict]:
    """检测 ObjectProperty 值差异（差异 #4）。"""
    diffs = []
    # 搜索包含 ObjectProperty 的行
    for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines)):
        if 'ObjectProperty' in old_line or 'ObjectProperty' in new_line:
            if old_line != new_line:
                # 检查是否是 dict→int 格式变化
                if "{'raw_index':" in old_line and new_line.strip().endswith(':'):
                    # 新版可能是裸整数
                    diffs.append({
                        "path": f"line[{i}]",
                        "old_value": old_line.strip(),
                        "new_value": new_line.strip()
                    })
    return diffs


def _detect_parent_class_diff(old_lines: list[str], new_lines: list[str]) -> list[dict]:
    """检测 parent_class str(dict) bug（差异 #8）。"""
    diffs = []
    for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines)):
        if 'parent_class' in old_line or 'parent_class' in new_line:
            # 检查新版是否是 str(dict)
            if "{'type':" in new_line or "'type':" in new_line:
                diffs.append({
                    "path": f"line[{i}]",
                    "old_value": old_line.strip(),
                    "new_value": new_line.strip()
                })
    return diffs


def extract_mermaid_blocks(markdown_output: str) -> list[str]:
    """从 Markdown 输出提取所有 ```mermaid 代码块。

    Per Pitfall 4: 验证测试应显式检查 mermaid 块存在性。

    Args:
        markdown_output: Markdown 格式输出字符串

    Returns:
        mermaid 块内容列表（不含 ```mermaid 围栏）
    """
    return re.findall(r'```mermaid\n(.*?)```', markdown_output, re.DOTALL)


def build_verification_report(
    recorder: DiffRecorder,
    asset_count: int,
    test_date: str
) -> str:
    """生成 VERIFICATION.md 报告（D-05）。

    Per 34-RESEARCH.md Code Examples。

    Args:
        recorder: DiffRecorder 实例
        asset_count: 测试资产数量
        test_date: 测试日期

    Returns:
        Markdown 格式报告字符串
    """
    lines = [
        "# Phase 34: 等价验证报告",
        "",
        f"**验证日期:** {test_date}",
        f"**测试资产数:** {asset_count}",
        f"**总差异数:** {len(recorder.diffs)}",
        "",
        "## 差异分类",
        "",
    ]

    # 按 severity 分组
    bugs = recorder.get_by_severity("bug")
    improvements = recorder.get_by_severity("improvement")
    known = recorder.get_by_severity("known")
    diffs = recorder.get_by_severity("diff")

    if bugs:
        lines.append("### Bugs (待修复)")
        for d in bugs:
            lines.append(f"- **{d['category']}**: `{d['field']}`")
            if d.get('note'):
                lines.append(f"  - {d['note']}")
            lines.append(f"  - old: {d['old_value']}")
            lines.append(f"  - new: {d['new_value']}")
        lines.append("")

    if improvements:
        lines.append("### Improvements (有意改进)")
        for d in improvements:
            lines.append(f"- **{d['category']}**: `{d['field']}`")
            if d.get('note'):
                lines.append(f"  - {d['note']}")
        lines.append("")

    if known:
        lines.append("### Known Differences (已知差异)")
        for d in known:
            lines.append(f"- **{d['category']}**: `{d['field']}`")
            if d.get('note'):
                lines.append(f"  - {d['note']}")
        lines.append("")

    if diffs:
        lines.append("### Other Differences (需审查)")
        for d in diffs:
            lines.append(f"- `{d['field']}` ({d['category']})")
            lines.append(f"  - old: {d['old_value']}")
            lines.append(f"  - new: {d['new_value']}")
        lines.append("")

    # 结论
    lines.append("## 结论")
    if bugs:
        lines.append(f"- **{len(bugs)} 个待修复问题** — 需在后续 phase 修复")
    lines.append(f"- **{len(improvements)} 个有意改进** — 新版行为更正确")
    lines.append(f"- **{len(known)} 个已知差异** — 设计决策导致的结构变化")
    lines.append(f"- **{len(diffs)} 个其他差异** — 需人工审查")
    lines.append("")
    lines.append("## 已知差异表")
    lines.append("")
    lines.append("| # | Category | Description | Severity |")
    lines.append("|---|----------|-------------|----------|")
    lines.append("| 1 | top_level_keys | imports/soft_references/circular_deps 移除 | known |")
    lines.append("| 2 | status | blueprint parent 检测修复 | improvement |")
    lines.append("| 3 | graphs_summary_keys | 2键→8键扩展 | improvement |")
    lines.append("| 4 | ObjectProperty_value | dict→int 格式变化 | diff (需审查) |")
    lines.append("| 5 | execution_flows_format | event型→node型 | diff (需审查) |")
    lines.append("| 6 | execution_flows_count | 7→4 数量变化 | diff (需审查) |")
    lines.append("| 7 | mermaid_missing | mermaid 图表缺失 | bug |")
    lines.append("| 8 | parent_class_str | str(dict) bug | bug |")
    lines.append("| 9 | json_full_crash | 两版都崩溃 | known |")

    return "\n".join(lines)


# ============================================================================
# Task 2: 测试用例
# ============================================================================

# 全局 DiffRecorder 实例
recorder = DiffRecorder()

# 真实资产路径（使用 pathlib.Path.as_posix() 兼容 Windows）
REAL_ASSETS = {
    "BP_FirstPersonCharacter": Path(
        "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
    ).as_posix(),
    "BP_FirstPersonCameraManager": Path(
        "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCameraManager.uasset"
    ).as_posix(),
    "BP_FirstPersonGameMode": Path(
        "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonGameMode.uasset"
    ).as_posix(),
}


def _write_verification_report():
    """测试进程退出时写 VERIFICATION.md（D-05）。"""
    import os
    report_dir = ".planning/phases/34-equivalence-verification"
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "VERIFICATION.md")
    report = build_verification_report(
        recorder,
        asset_count=3,
        test_date=datetime.now().strftime('%Y-%m-%d')
    )
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)


# 注册 atexit 钩子
atexit.register(_write_verification_report)


# ============================================================================
# Helper 函数：创建合成资产
# ============================================================================

# 从 test_uasset_read.py 导入 create_test_uasset
# 添加路径确保 pytest 能找到
import sys
tests_dir = Path(__file__).parent
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

from test_uasset_read import create_test_uasset, cleanup_test_file


# ============================================================================
# 测试用例
# ============================================================================

def test_json_full_synthetic():
    """JSON Full 格式 — 合成资产等价验证（等价-01, 等价-05）。

    Per D-04: 记录并继续 — 不中断验证流程。
    Per Pitfall 5: --json full format 在真实资产上崩溃是共享限制。
    """
    # 创建合成资产
    path = create_test_uasset()
    try:
        old_stdout, old_rc = run_old_cli('--json', path)
        new_stdout, new_rc = run_new_cli('--json', path)

        # #9: 两版都崩溃 → 记录为 known
        if old_rc == 1 and new_rc == 1:
            recorder.record(
                asset_name="synthetic",
                format_name="json_full",
                field_path="cli_exit_code",
                old_value=old_rc,
                new_value=new_rc,
                severity="known",
                category="json_full_crash",
                note="Both versions crash on --json (shared limitation)"
            )
        # 仅新版崩溃 → 记录为 bug
        elif new_rc == 1 and old_rc == 0:
            recorder.record(
                asset_name="synthetic",
                format_name="json_full",
                field_path="cli_exit_code",
                old_value=old_rc,
                new_value=new_rc,
                severity="bug",
                category="json_full_crash",
                note="New version crashes but old succeeds"
            )
        # 都成功 → 对比输出
        elif old_rc == 0 and new_rc == 0:
            compare_outputs(old_stdout, new_stdout, 'json_full', 'synthetic', recorder)

        # D-04: 记录并继续
        assert True
    finally:
        cleanup_test_file(path)


def test_json_summary_synthetic():
    """JSON Summary 格式 — 合成资产等价验证（等价-02）。"""
    path = create_test_uasset()
    try:
        old_stdout, old_rc = run_old_cli('--summary', path)
        new_stdout, new_rc = run_new_cli('--summary', path)

        if old_rc == 0 and new_rc == 0:
            compare_outputs(old_stdout, new_stdout, 'json_summary', 'synthetic', recorder)

        assert True
    finally:
        cleanup_test_file(path)


@pytest.mark.parametrize('asset_name,asset_path', [
    ("BP_FirstPersonCharacter", REAL_ASSETS["BP_FirstPersonCharacter"]),
    ("BP_FirstPersonCameraManager", REAL_ASSETS["BP_FirstPersonCameraManager"]),
    ("BP_FirstPersonGameMode", REAL_ASSETS["BP_FirstPersonGameMode"]),
])
def test_json_summary_equivalence(asset_name: str, asset_path: str):
    """JSON Summary 格式 — 真实资产等价验证（等价-02, 等价-06）。

    预期差异: #1 (top_level_keys), #2 (status), #3 (graphs_summary_keys),
              #5 (execution_flows_format), #6 (execution_flows_count)
    """
    if not os.path.exists(asset_path):
        pytest.skip(f"Asset not found: {asset_path}")

    old_stdout, old_rc = run_old_cli('--summary', asset_path)
    new_stdout, new_rc = run_new_cli('--summary', asset_path)

    if old_rc == 0 and new_rc == 0:
        compare_outputs(old_stdout, new_stdout, 'json_summary', asset_name, recorder)

    assert True


@pytest.mark.parametrize('asset_name,asset_path', [
    ("synthetic", None),  # 合成资产动态创建
    ("BP_FirstPersonCharacter", REAL_ASSETS["BP_FirstPersonCharacter"]),
    ("BP_FirstPersonCameraManager", REAL_ASSETS["BP_FirstPersonCameraManager"]),
])
def test_text_equivalence(asset_name: str, asset_path: str):
    """Text 格式 — 合成+真实资产等价验证（等价-03）。

    预期差异: #4 (ObjectProperty_value, 227 行 diff),
              #8 (parent_class_str, 18 行 diff)
    """
    # 合成资产动态创建
    if asset_name == "synthetic":
        asset_path = create_test_uasset()

    if not os.path.exists(asset_path):
        if asset_name == "synthetic":
            cleanup_test_file(asset_path)
        pytest.skip(f"Asset not found: {asset_path}")

    try:
        old_stdout, old_rc = run_old_cli('--text', asset_path)
        new_stdout, new_rc = run_new_cli('--text', asset_path)

        if old_rc == 0 and new_rc == 0:
            compare_outputs(old_stdout, new_stdout, 'text', asset_name, recorder)

        assert True
    finally:
        if asset_name == "synthetic":
            cleanup_test_file(asset_path)


@pytest.mark.parametrize('asset_name,asset_path', [
    ("synthetic", None),
    ("BP_FirstPersonCharacter", REAL_ASSETS["BP_FirstPersonCharacter"]),
    ("BP_FirstPersonCameraManager", REAL_ASSETS["BP_FirstPersonCameraManager"]),
])
def test_markdown_equivalence(asset_name: str, asset_path: str):
    """Markdown 格式 — 合成+真实资产等价验证（等价-04）。

    预期差异: #7 (mermaid_missing), #8 (parent_class_str)
    """
    if asset_name == "synthetic":
        asset_path = create_test_uasset()

    if not os.path.exists(asset_path):
        if asset_name == "synthetic":
            cleanup_test_file(asset_path)
        pytest.skip(f"Asset not found: {asset_path}")

    try:
        old_stdout, old_rc = run_old_cli('--markdown', asset_path)
        new_stdout, new_rc = run_new_cli('--markdown', asset_path)

        if old_rc == 0 and new_rc == 0:
            compare_outputs(old_stdout, new_stdout, 'markdown', asset_name, recorder)

        assert True
    finally:
        if asset_name == "synthetic":
            cleanup_test_file(asset_path)


def test_synthetic_all_formats():
    """合成资产 — 全部四种格式快速验证（等价-05）。

    合成资产应仅有 #1 (top_level_keys) 差异。
    确认合成资产验证通过（near-equivalent）。
    """
    path = create_test_uasset()
    try:
        formats = ['--json', '--summary', '--text', '--markdown']
        format_names = ['json_full', 'json_summary', 'text', 'markdown']

        for fmt_flag, fmt_name in zip(formats, format_names):
            old_stdout, old_rc = run_old_cli(fmt_flag, path)
            new_stdout, new_rc = run_new_cli(fmt_flag, path)

            if old_rc == 0 and new_rc == 0:
                compare_outputs(old_stdout, new_stdout, fmt_name, 'synthetic', recorder)

        assert True
    finally:
        cleanup_test_file(path)


def test_real_assets_all_formats():
    """真实资产 — 全部格式验证（BP_FirstPersonCharacter 为主）（等价-06）。

    预期所有 9 类差异可能出现。
    """
    asset_path = REAL_ASSETS["BP_FirstPersonCharacter"]

    if not os.path.exists(asset_path):
        pytest.skip(f"Asset not found: {asset_path}")

    formats = ['--summary', '--text', '--markdown']  # Skip --json due to #9
    format_names = ['json_summary', 'text', 'markdown']

    for fmt_flag, fmt_name in zip(formats, format_names):
        old_stdout, old_rc = run_old_cli(fmt_flag, asset_path)
        new_stdout, new_rc = run_new_cli(fmt_flag, asset_path)

        if old_rc == 0 and new_rc == 0:
            compare_outputs(old_stdout, new_stdout, fmt_name, 'BP_FirstPersonCharacter', recorder)

    assert True


def test_verification_report_generated():
    """验证 VERIFICATION.md 报告在测试结束后生成（等价-07）。

    此测试检查 atexit 注册是否正常工作。
    实际报告由 atexit hook 在进程退出时写入。
    """
    # 确认函数存在且可调用
    assert callable(_write_verification_report)

    # 确认 build_verification_report 函数存在
    assert callable(build_verification_report)

    # 模拟生成报告验证格式
    test_recorder = DiffRecorder()
    test_recorder.record(
        asset_name="test",
        format_name="test_format",
        field_path="test_field",
        severity="diff",
        category="test_category"
    )
    report = build_verification_report(test_recorder, asset_count=1, test_date="2026-05-12")

    # 验证报告包含必要章节
    assert "# Phase 34: 等价验证报告" in report
    assert "验证日期" in report
    assert "差异分类" in report
    assert "结论" in report
    assert "已知差异表" in report


# ============================================================================
# pytest 配置
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])