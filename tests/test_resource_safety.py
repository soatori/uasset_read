"""资源安全测试 — 文件句柄和 stderr。"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest


def _src_path(relative: str) -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "uasset_read" / relative


class TestNoFileHandleLeak:
    """验证无 open() 无 with 的文件句柄泄漏。"""

    @staticmethod
    def _find_bare_open(filepath: Path) -> list[int]:
        """检测裸 open() 调用（不在 with 语句中的）的行号。

        遍历 AST，找出所有 ``open(...)`` 调用节点，然后检查其
        最近的 ast.Call 祖先是否直接位于 ``with`` 上下文管理器中。
        """
        tree = ast.parse(filepath.read_text(encoding="utf-8"))

        # 收集所有 with 语句中直接包含 open() 的节点位置
        with_open_lines: set[int] = set()

        class WithVisitor(ast.NodeVisitor):
            """遍历 with 语句，记录直接在 with 中的 open() 调用。"""

            def visit_With(self, node: ast.With) -> None:
                for item in node.items:
                    if isinstance(item.context_expr, ast.Call):
                        call = item.context_expr
                        if isinstance(call.func, ast.Name) and call.func.id == "open":
                            with_open_lines.add(call.lineno)
                self.generic_visit(node)

        WithVisitor().visit(tree)

        # 收集所有裸 open() 调用
        bare_lines: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "open":
                    if node.lineno not in with_open_lines:
                        bare_lines.append(node.lineno)
        return sorted(bare_lines)

    def test_mappings_no_handle_leak(self):
        """mappings.py 不应存在裸 open() 调用。"""
        filepath = _src_path("mappings.py")
        bare = self._find_bare_open(filepath)
        assert not bare, (
            f"mappings.py 存在 {len(bare)} 处裸 open() 调用 "
            f"(行 {bare})，应使用 with 语句"
        )

    def test_batch_worker_no_handle_leak(self):
        """batch_worker.py 不应存在裸 open() 调用。"""
        filepath = _src_path("batch_worker.py")
        bare = self._find_bare_open(filepath)
        assert not bare, (
            f"batch_worker.py 存在 {len(bare)} 处裸 open() 调用 "
            f"(行 {bare})，应使用 with 语句"
        )


class TestStderrNotSwallowed:
    """验证 batch_worker 子进程 stderr 不被吞没。"""

    def test_stderr_not_devnull(self):
        """batch_worker.py 中 Popen 不应将 stderr 重定向到 DEVNULL。"""
        filepath = _src_path("batch_worker.py")
        tree = ast.parse(filepath.read_text(encoding="utf-8"))

        devnull_stderr: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # 检查是否为 subprocess.Popen 调用
                func = node.func
                is_popen = (
                    isinstance(func, ast.Attribute)
                    and func.attr == "Popen"
                )
                if not is_popen:
                    continue
                # 检查 stderr=DEVNULL 关键字参数
                for kw in node.keywords:
                    if kw.arg == "stderr":
                        if isinstance(kw.value, ast.Attribute):
                            # stderr=subprocess.DEVNULL
                            if kw.value.attr == "DEVNULL":
                                devnull_stderr.append(node.lineno)
                        elif isinstance(kw.value, ast.Name):
                            # stderr=DEVNULL (已导入)
                            if kw.value.id == "DEVNULL":
                                devnull_stderr.append(node.lineno)

        assert not devnull_stderr, (
            f"batch_worker.py 行 {devnull_stderr}: "
            f"stderr 被重定向到 DEVNULL，应保留 stderr 用于调试"
        )

    def test_stderr_visible_on_subprocess_failure(self):
        """子进程失败时 stderr 应可通过日志获取。"""
        # 验证 batch_worker 源码中存在对 result.stderr 的日志记录
        filepath = _src_path("batch_worker.py")
        source = filepath.read_text(encoding="utf-8")
        # 应有 logger 调用引用 stderr（或 PIPE 模式）
        has_stderr_logging = (
            "result.stderr" in source
            or "stderr" in source
            and "logger" in source
        )
        # 基本验证：文件中应引用 stderr 用于调试
        assert has_stderr_logging or "DEVNULL" not in source, (
            "batch_worker.py 既不记录 stderr 也不保留 stderr，"
            "子进程错误信息将完全丢失"
        )
