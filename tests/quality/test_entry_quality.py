"""入口合同测试。"""
from __future__ import annotations

import ast
import importlib
import inspect

import pytest
import uasset_read
from uasset_read import core
from uasset_read.pak.constants import PAK_INFO_SIZES


class TestEntryContracts:
    """入口模块与公共 API 的稳定合同。"""

    def test_public_api_exports_and_list_formats(self):
        """包级公共 API 可导出且 list_formats 返回常见格式。"""
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
