"""quality_stats.py 脚本功能验证测试。

验证 C++ 质量统计脚本的基本功能、指标检测和 fatal gate 行为。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "quality_stats.py"

pytestmark = pytest.mark.auxiliary


def _run(args=None, cwd=None):
    """运行 quality_stats.py 并返回 (returncode, stdout, stderr)。"""
    cmd = [sys.executable, str(_SCRIPT)]
    if args:
        cmd.extend(args)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        cmd, capture_output=True, cwd=cwd, env=env,
        encoding="utf-8", errors="replace",
    )
    return result.returncode, result.stdout, result.stderr


class TestQualityStatsCLI:
    """CLI 参数处理测试。"""

    def test_help_exits_clean(self):
        rc, out, err = _run(["--help"])
        assert rc == 0
        assert "scan_dir" in out or "usage" in out.lower()

    def test_missing_scan_dir_errors(self):
        rc, out, err = _run()
        assert rc != 0


class TestQualityStatsMetrics:
    """指标检测测试 — 使用合成 C++ 文件。"""

    def _write_cpp(self, tmp_path, content, name="test.cpp"):
        path = tmp_path / name
        path.write_text(content)
        return str(tmp_path)

    def test_detects_function_placeholder(self, tmp_path):
        """Function_N 占位符应被检测并报告为 FAIL。"""
        cpp_dir = self._write_cpp(tmp_path, """
void UTestClass::SomeFunction()
{
    CallFunction_42(arg1);
    CallFunction_99(arg2);
}
""")
        rc, out, err = _run([cpp_dir])
        # 检测到占位符时应失败（exit code 1）
        assert rc != 0 or "FAIL" in out
        assert "Function_N" in out or "占位" in out

    def test_detects_goto_fallback(self, tmp_path):
        """goto Label_ 回退应被检测。"""
        cpp_dir = self._write_cpp(tmp_path, """
void UTestClass::ExecuteUbergraph()
{
    goto Label_1;
Label_1:
    goto Label_2;
Label_2:
    return;
}
""")
        rc, out, err = _run([cpp_dir])
        # 可能有 goto，脚本应报告
        assert "goto" in out.lower()

    def test_json_output_valid(self, tmp_path):
        """--json 输出应为有效 JSON。"""
        cpp_dir = self._write_cpp(tmp_path, """
void UTestClass::Test()
{
    return;
}
""")
        rc, out, err = _run([cpp_dir, "--json"])
        assert rc == 0
        data = json.loads(out)
        assert isinstance(data, dict)

    def test_threshold_flag_custom(self, tmp_path):
        """--threshold 应使用自定义阈值。"""
        cpp_dir = self._write_cpp(tmp_path, """
void UTestClass::Test() { return; }
""")
        rc, out, err = _run([cpp_dir, "--threshold", "5"])
        assert rc == 0

    def test_verbose_flag_output(self, tmp_path):
        """--verbose 应输出每个文件详细统计。"""
        cpp_dir = self._write_cpp(tmp_path, """
void UTestClass::Test() { return; }
""")
        rc, out, err = _run([cpp_dir, "--verbose"])
        assert rc == 0
        assert len(out) > 0

    def test_zero_files_returns_fail(self, tmp_path):
        """零文件时应返回非零 exit code。"""
        rc, out, err = _run([str(tmp_path)])
        assert rc != 0, "零文件时不应返回 PASS"
        combined = out + err
        assert "未找到" in combined or "no files" in combined.lower() or "FAIL" in combined

    def test_clean_cpp_passes(self, tmp_path):
        """清洁的 C++ 输出应全部通过。"""
        cpp_dir = self._write_cpp(tmp_path, """
// TestClass.cpp
#include "TestClass.h"

void UTestClass::TestMethod(int Param)
{
    SomeFunction(Param);
}
""")
        rc, out, err = _run([cpp_dir])
        assert rc == 0
        assert "PASS" in out
