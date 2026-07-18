"""质量门禁测试 — 合并自 tests/quality/ 目录。

覆盖：
- 代码质量检查：AST 扫描验证
- 入口合同测试
- 测试套件形状检查
"""
# ─── test_code_quality.py ─────────────────────────────────────────────
import ast
import inspect
import os
import sys
from pathlib import Path

import pytest
import uasset_read
from uasset_read import core
from uasset_read.pak.constants import PAK_INFO_SIZES


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


# ─── test_entry_quality.py ────────────────────────────────────────────


class TestEntryContracts:
    """入口模块与公共 API 的稳定合同。"""

    def test_public_api_exports_and_list_formats(self):
        """包级公共 API 可导出且 list_formats 返回常见格式。"""
        import importlib
        importlib.reload(uasset_read)

        for name in ("parse_single", "parse_batch", "list_formats"):
            assert hasattr(uasset_read, name)
            assert callable(getattr(uasset_read, name))
            assert name in uasset_read.__all__

        formats = uasset_read.list_formats()
        assert {"json", "markdown"}.issubset(set(formats))

    def test_entrypoint_symbols_are_callable(self):
        """入口模块导出的函数应可调用。"""
        from uasset_read.parse_uasset import (
            parse_package,
            parse_package_lazy,
            parse_uasset,
            parse_uasset_with_linker,
        )

        for func in (parse_package, parse_package_lazy, parse_uasset, parse_uasset_with_linker):
            assert callable(func)

    def test_parse_package_signature(self):
        """parse_package 签名应包含核心参数。"""
        from uasset_read.parse_uasset import parse_package

        sig = inspect.signature(parse_package)
        params = sig.parameters
        required = {"path", "tolerant", "provider", "mappings_path", "game", "force_full_parse"}
        assert required.issubset(params)
        assert "return" in parse_package.__annotations__

    def test_core_parse_signatures_stay_aligned(self):
        """parse_single 与 parse_batch 的共享参数默认值应保持一致。"""
        single_sig = inspect.signature(core.parse_single)
        batch_sig = inspect.signature(core.parse_batch)

        for name in ("tolerant", "verbose", "include_schema", "include_function_graphs", "include_parent_assets", "asset_roots", "mappings_path", "game", "force_full_parse", "hex_view", "memory_policy", "output_level"):
            assert name in single_sig.parameters
            assert name in batch_sig.parameters
            assert batch_sig.parameters[name].default == single_sig.parameters[name].default

        assert "input_dir" in batch_sig.parameters
        assert "file_path" in single_sig.parameters
        assert "return" in core.parse_batch.__annotations__

    def test_entry_modules_delegate_without_print_or_sys_exit(self):
        """入口模块不应包含 sys.exit / print，parse_uasset 仍应委托给 parse_package。"""
        import importlib
        parse_uasset_mod = importlib.import_module("uasset_read.parse_uasset")

        for mod in (parse_uasset_mod, core):
            src = inspect.getsource(mod)
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute) and func.attr == "exit":
                        if isinstance(func.value, ast.Name) and func.value.id == "sys":
                            pytest.fail(f"{mod.__name__} 第 {node.lineno} 行包含 sys.exit() 调用")
                    if isinstance(func, ast.Name) and func.id == "print":
                        pytest.fail(f"{mod.__name__} 第 {node.lineno} 行包含 print() 调用")

        assert "parse_package" in inspect.getsource(parse_uasset_mod.parse_uasset)
        assert "linker_formats" in inspect.getsource(core.parse_single)

    def test_pak_info_size_contract(self):
        """PAK_INFO_SIZES 应保持当前已知序列化大小。"""
        expected = {
            "v1-6": 45,
            "v7": 61,
            "v8": 221,
            "v9": 222,
            "v10+": 221,
        }
        for version, size in expected.items():
            assert PAK_INFO_SIZES[version] == size


# ─── test_suite_shape.py ──────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"


def test_total_test_file_count_is_capped():
    files = sorted(TESTS.rglob("test_*.py"))
    assert len(files) <= 100


def test_core_benchmark_file_count_is_capped():
    files = sorted((TESTS / "integration").glob("test_*.py"))
    assert len(files) <= 10
