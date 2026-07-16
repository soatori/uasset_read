"""静默异常吞没检测测试。"""
import ast
import os
import pytest


class TestNoSilentExceptions:
    """验证无 except + pass 的静默吞没。"""

    def _find_silent_exceptions(self, filepath):
        """检测文件中的 except + pass 模式。"""
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                        issues.append(f"行 {handler.lineno}: except {handler.type}")
        return issues

    def test_src_no_silent_exceptions(self):
        """src/ 目录下应无静默异常吞没（允许已知的安全网和清理代码）。"""
        src_dir = os.path.join(os.path.dirname(__file__), "..", "src", "uasset_read")
        # 允许的静默异常模式（cleanup/safety-net），匹配相对路径
        allowed_files = {
            "archive.py",  # __del__ 安全网
            "parse_uasset.py",  # 清理代码
            "core/__init__.py",  # 清理代码
            "iostore/reader.py",  # 安全网
            "pak/reader.py",  # 安全网
        }
        all_issues = []
        for root, _, files in os.walk(src_dir):
            for f in files:
                if f.endswith(".py"):
                    filepath = os.path.join(root, f)
                    # 计算相对路径用于匹配
                    rel_path = os.path.relpath(filepath, src_dir).replace(os.sep, "/")
                    if rel_path in allowed_files:
                        continue
                    issues = self._find_silent_exceptions(filepath)
                    for issue in issues:
                        all_issues.append(f"{filepath}: {issue}")
        assert len(all_issues) == 0, (
            f"发现 {len(all_issues)} 处静默异常吞没:\n" + "\n".join(all_issues[:10])
        )
