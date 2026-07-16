"""代码质量检查：AST 扫描验证（合并自 3 个独立 lint 测试）"""
import ast
import inspect
import os
import sys

import pytest


# ─── 静默异常检测 ──────────────────────────────────────────────────────


def _find_silent_exceptions(filepath):
    """检测文件中的 except + pass 模式（允许已知的安全网和清理代码）"""
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                    issues.append(f"行 {handler.lineno}: except {handler.type}")
    return issues


def test_no_silent_exceptions():
    """src/ 目录下应无静默异常吞没（允许已知的安全网和清理代码）"""
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
                issues = _find_silent_exceptions(filepath)
                for issue in issues:
                    all_issues.append(f"{filepath}: {issue}")
    assert len(all_issues) == 0, (
        f"发现 {len(all_issues)} 处静默异常吞没:\n" + "\n".join(all_issues[:10])
    )


# ─── 可变默认参数检测 ─────────────────────────────────────────────────


def test_flow_builder_no_mutable_defaults():
    """flow_builder 应无可变默认参数"""
    from uasset_read.graph import flow_builder

    issues = []
    for name, obj in inspect.getmembers(flow_builder, inspect.isfunction):
        sig = inspect.signature(obj)
        for param_name, param in sig.parameters.items():
            if param.default is not inspect.Parameter.empty:
                if isinstance(param.default, (dict, list, set)):
                    issues.append(f"{name}({param_name}={param.default})")
    assert len(issues) == 0, f"flow_builder 存在可变默认参数: {issues}"


# ─── 核心导入分层验证 ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "needle",
    ["kismet", "cpp_gen", "graph", "pak", "iostore"],
)
def test_core_import_does_not_load_extras(needle: str):
    """导入 parse_package 不应加载 extras 模块"""
    modules_before = set(sys.modules.keys())
    from uasset_read.parse_uasset import parse_package
    modules_after = set(sys.modules.keys())
    new_modules = modules_after - modules_before
    assert not any(needle in m for m in new_modules), (
        f"parse_package 导入意外加载了 {needle} 模块: "
        f"{[m for m in sorted(new_modules) if needle in m]}"
    )


# ─── FULL_SERIALIZER 清理验证 ─────────────────────────────────────────


def test_full_serializer_not_used():
    """SerializationStrategy.FULL_SERIALIZER 不应在生产代码中使用。"""
    from uasset_read.parsers.class_serialization_strategy import CLASS_STRATEGY_TABLE
    for cls, strategy in CLASS_STRATEGY_TABLE.items():
        assert strategy.value != "full_serializer", (
            f"{cls} 使用了未实现的 FULL_SERIALIZER 策略"
        )


def test_full_serializer_removed_from_enum():
    """FULL_SERIALIZER 已从 SerializationStrategy 枚举中移除。"""
    from uasset_read.parsers.class_serialization_strategy import SerializationStrategy
    assert not hasattr(SerializationStrategy, "FULL_SERIALIZER"), (
        "FULL_SERIALIZER 仍存在于 SerializationStrategy 枚举中"
    )


# ─── include_linker 废弃验证 ─────────────────────────────────────────


def test_include_linker_deprecated():
    """parse_package() 的 include_linker 参数应触发 DeprecationWarning。"""
    from uasset_read.parse_uasset import parse_package

    # 参数应仍然存在于签名中（向后兼容）
    sig = inspect.signature(parse_package)
    assert "include_linker" in sig.parameters

    # 非默认值应触发 DeprecationWarning
    with pytest.warns(DeprecationWarning, match="include_linker"):
        try:
            parse_package("nonexistent.uasset", include_linker=False)
        except (FileNotFoundError, ValueError):
            pass  # 预期失败，但警告应该已经触发
