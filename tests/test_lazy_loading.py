"""懒加载导出对象测试 — ExportIR 字段 + parse_package_lazy 函数。"""
import pytest
from pathlib import Path

from uasset_read.models.ir import ExportIR, ExportRawIR, PackageIR, PackageHeaderIR
from uasset_read.models.result import ParseResult


class TestExportIRLazyFields:
    """测试 ExportIR 懒加载字段。"""

    def _make_export(self):
        return ExportIR(
            index=0,
            object_name="Test",
            object_class="StaticMesh",
            serial_size=1000,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
        )

    def test_export_ir_has_is_loaded(self):
        """ExportIR 包含 is_loaded 标记，默认 False"""
        export = self._make_export()
        assert hasattr(export, "is_loaded")
        assert export.is_loaded is False

    def test_export_ir_has_lazy_load_archive(self):
        """ExportIR 包含 lazy_load_archive 字段，默认 None"""
        export = self._make_export()
        assert hasattr(export, "lazy_load_archive")
        assert export.lazy_load_archive is None

    def test_export_ir_lazy_fields_can_be_set(self):
        """懒加载字段可被设置"""
        export = self._make_export()
        export.is_loaded = True
        export.lazy_load_archive = b"\x00\x01\x02"
        assert export.is_loaded is True
        assert export.lazy_load_archive == b"\x00\x01\x02"


class TestParsePackageLazy:
    """测试 parse_package_lazy 函数。"""

    def _get_test_asset(self):
        """获取一个可用的测试 .uasset 文件路径"""
        samples = Path(__file__).parent / "samples"
        if not samples.exists():
            pytest.skip("测试样本目录不存在")
        assets = list(samples.glob("*.uasset"))
        if not assets:
            pytest.skip("无可用 .uasset 测试文件")
        return str(assets[0])

    def test_parse_lazy_returns_result(self):
        """parse_package_lazy 返回 ParseResult"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(path, tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.summary is not None
        assert result.name_map is not None

    def test_parse_lazy_no_indices_all_unloaded(self):
        """未指定 export_indices 时所有 export 标记为未加载"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(path, export_indices=None, tolerant=True)
        for export in result.export_map:
            assert export.is_loaded is False

    def test_parse_lazy_with_indices(self):
        """指定 export_indices 时对应 export 被加载"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(path, tolerant=True)
        if not result.export_map:
            pytest.skip("测试文件无 export")

        # 只加载第一个 export
        result2 = parse_package_lazy(path, export_indices=[0], tolerant=True)
        assert result2.export_map[0].is_loaded is True
        for i in range(1, len(result2.export_map)):
            assert result2.export_map[i].is_loaded is False

    def test_parse_lazy_store_raw_bytes(self):
        """store_raw_bytes=True 时 export 包含原始字节"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(
            path, export_indices=[], store_raw_bytes=True, tolerant=True,
        )
        for export in result.export_map:
            if export.serial_size > 0:
                assert export.lazy_load_archive is not None
                assert isinstance(export.lazy_load_archive, bytes)

    def test_parse_lazy_no_raw_bytes(self):
        """store_raw_bytes=False 时 export 不包含原始字节"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(
            path, export_indices=[], store_raw_bytes=False, tolerant=True,
        )
        for export in result.export_map:
            assert getattr(export, "lazy_load_archive", None) is None

    def test_parse_lazy_metadata(self):
        """parse_package_lazy 设置正确的 metadata"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(
            path, export_indices=[0], tolerant=True,
        )
        assert result.metadata.get("lazy_loading") is True
        assert 0 in result.metadata.get("loaded_exports", [])
        assert "total_exports" in result.metadata

    def test_parse_lazy_nonexistent_index(self):
        """指定不存在的 export_indices 不会崩溃"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(
            path, export_indices=[9999], tolerant=True,
        )
        # 所有 export 仍应标记为未加载
        for export in result.export_map:
            assert export.is_loaded is False
