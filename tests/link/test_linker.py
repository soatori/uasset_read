"""tests/link/test_linker.py — PackageLinker 验证逻辑测试。

验证：
1. _verify_imports() 返回值被 post_load() 保留
2. post_load() 将导入验证错误传播到 _import_verification_errors
3. 无错误时 _import_verification_errors 为空列表
"""
import pytest
from unittest.mock import MagicMock, patch

from uasset_read.link.linker import PackageLinker
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.serializers.object_resources import PackageIndex, ObjectImport, ObjectExport


def _make_linker(
    import_count: int = 2,
    export_count: int = 1,
    file_size: int = 1024,
) -> PackageLinker:
    """创建一个用于测试的 PackageLinker 实例。"""
    archive = MagicMock()
    archive._file_size = file_size
    summary = MagicMock()
    summary.depends_map = None
    name_map = ["TestName"]

    import_map = []
    for i in range(import_count):
        imp = MagicMock()
        imp.object_name = f"Import_{i}"
        imp.class_name = f"Class_{i}"
        imp.class_package = f"/Script/Engine"
        imp.outer_index = PackageIndex(0)
        imp.class_index = PackageIndex(0)
        import_map.append(imp)

    export_map = []
    for i in range(export_count):
        exp = MagicMock()
        exp.object_name = f"Export_{i}"
        exp.class_index = PackageIndex(-(1)) if import_count > 0 else PackageIndex(0)
        exp.outer_index = PackageIndex(0)
        exp.super_index = PackageIndex(0)
        exp.template_index = PackageIndex(0)
        exp.serial_offset = 0
        exp.serial_size = 0
        export_map.append(exp)

    linker = PackageLinker(archive, summary, name_map, import_map, export_map)
    linker.link()
    return linker


class TestVerifyImportsReturnValue:
    """_verify_imports() 返回值保留。"""

    def test_import_verification_errors_initialized_empty(self):
        """_import_verification_errors 初始为空列表。"""
        linker = _make_linker()
        assert linker._import_verification_errors == []

    def test_post_load_captures_verify_imports_result(self):
        """post_load() 将 _verify_imports() 结果保存到 _import_verification_errors。"""
        linker = _make_linker(import_count=2)
        # 正常情况：无验证错误
        linker.post_load()
        assert isinstance(linker._import_verification_errors, list)
        assert linker._import_verification_errors == []

    def test_post_load_with_broken_outer_index(self):
        """outer_index 越界时 _verify_imports 返回错误。"""
        linker = _make_linker(import_count=2, export_count=1)
        linker._import_map[1].outer_index = PackageIndex(999)

        linker.post_load()

        assert len(linker._import_verification_errors) > 0
        assert any("outer_index" in e for e in linker._import_verification_errors)

    def test_verify_imports_returns_list(self):
        """_verify_imports() 返回类型为 List[str]。"""
        linker = _make_linker()
        result = linker._verify_imports()
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, str)

    def test_verify_imports_empty_on_valid_data(self):
        """所有引用有效时 _verify_imports() 返回空列表。"""
        linker = _make_linker(import_count=2, export_count=1)
        # 所有 import 的 class_index 和 outer_index 都是 null（不触发验证）
        errors = linker._verify_imports()
        assert errors == []


class TestPostLoadPreservesVerifyResult:
    """post_load() 保留 _verify_imports 返回值的集成验证。"""

    def test_errors_stored_on_linker(self):
        """post_load 后错误可通过 linker._import_verification_errors 访问。"""
        linker = _make_linker(import_count=1, export_count=1)
        linker._import_map[0].outer_index = PackageIndex(999)

        linker.post_load()

        # 错误应可从 linker 实例访问
        errors = linker._import_verification_errors
        assert isinstance(errors, list)
        assert len(errors) >= 1
        # 每个错误是描述性字符串
        for err in errors:
            assert isinstance(err, str)
            assert len(err) > 0

    def test_multiple_errors_captured(self):
        """多个 import 引用错误都被捕获。"""
        linker = _make_linker(import_count=3, export_count=1)
        # 三个 import 的 outer_index 都越界
        for i in range(3):
            linker._import_map[i].outer_index = PackageIndex(999)

        linker.post_load()

        assert len(linker._import_verification_errors) >= 3
