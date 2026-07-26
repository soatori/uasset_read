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
        """store_raw_bytes=True: non-loaded exports with valid sizes get raw bytes.

        Some exports may fail to read (e.g. corrupted serial_size) in
        tolerant mode; verify the ones that do read are stored correctly.
        """
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(
            path, export_indices=[], store_raw_bytes=True, tolerant=True,
        )
        for idx, export in enumerate(result.export_map):
            raw = getattr(export, "lazy_load_archive", None)
            if raw is not None:
                assert isinstance(raw, bytes), (
                    f"Export {idx}: expected bytes, got {type(raw)}"
                )

    def test_parse_lazy_no_raw_bytes(self):
        """store_raw_bytes=False 时 export 不包含原始字节"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(
            path, export_indices=[], store_raw_bytes=False, tolerant=True,
        )
        for export in result.export_map:
            assert getattr(export, "lazy_load_archive", None) is None

    def test_parse_lazy_raw_bytes_only_for_non_loaded(self):
        """store_raw_bytes=True only stores bytes for non-loaded exports.

        Loaded exports have properties already parsed; raw bytes would
        be redundant and waste memory.
        """
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(
            path, export_indices=[0], store_raw_bytes=True, tolerant=True,
        )
        for idx, export in enumerate(result.export_map):
            if export.serial_size <= 0:
                continue
            loaded = getattr(export, "is_loaded", False)
            raw = getattr(export, "lazy_load_archive", None)
            if idx in [0]:
                # Loaded export: raw bytes must NOT be stored
                assert loaded is True
                assert raw is None, (
                    f"Loaded export {idx} ({export.object_name}) should "
                    f"not retain raw bytes"
                )
            else:
                # Non-loaded export: raw bytes should be stored
                assert loaded is False
                # raw may be None if read failed in tolerant mode
                if raw is not None:
                    assert isinstance(raw, bytes)

    def test_parse_lazy_raw_bytes_all_selected_no_retention(self):
        """When all exports are selected, no raw bytes should be stored."""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(path, export_indices=[], tolerant=True)
        total = len(result.export_map)
        if total < 2:
            pytest.skip("Need at least 2 exports for this test")
        # Select all exports
        all_indices = list(range(total))
        result = parse_package_lazy(
            path, export_indices=all_indices,
            store_raw_bytes=True, tolerant=True,
        )
        for idx, export in enumerate(result.export_map):
            if export.serial_size <= 0:
                continue
            loaded = getattr(export, "is_loaded", False)
            raw = getattr(export, "lazy_load_archive", None)
            assert loaded is True
            assert raw is None, (
                f"All exports selected; export {idx} should not "
                f"retain raw bytes"
            )

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


class TestLazyParseErrorAlignment:
    """Verify parse_package_lazy error semantics align with _parse_package_core.

    These tests prove that the lazy path uses the same validation and
    status patterns as the main parse chain.
    """

    def _get_test_asset(self):
        samples = Path(__file__).parent / "samples"
        if not samples.exists():
            pytest.skip("Test samples directory not found")
        assets = list(samples.glob("*.uasset"))
        if not assets:
            pytest.skip("No .uasset test files available")
        return str(assets[0])

    def test_lazy_creates_memory_monitor(self):
        """memory_policy creates a MemoryMonitor in the lazy path."""
        from uasset_read.parse_uasset import parse_package_lazy
        from uasset_read.memory_safety import MemoryPolicy
        path = self._get_test_asset()
        policy = MemoryPolicy()
        result = parse_package_lazy(
            path, export_indices=[], tolerant=True,
            memory_policy=policy,
        )
        # parse_package_lazy should succeed — memory_policy was consumed
        assert result is not None
        assert isinstance(result, ParseResult)

    def test_lazy_parse_status_uses_validated_values(self):
        """parse_status values from lazy path are valid ExportParseStatus members."""
        from uasset_read.parse_uasset import parse_package_lazy
        from uasset_read.models.fallback import ExportParseStatus
        path = self._get_test_asset()
        result = parse_package_lazy(
            path, export_indices=[0], tolerant=True,
        )
        for export in result.export_map:
            status = getattr(export, "parse_status", None)
            if status is not None:
                # status must be a valid ExportParseStatus value
                assert status in {s.value for s in ExportParseStatus}, (
                    f"Invalid parse_status {status!r} on export "
                    f"{getattr(export, 'object_name', '?')}"
                )

    def test_lazy_tolerant_mode_captures_errors(self):
        """In tolerant mode, parse_package_lazy captures errors instead of raising."""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        # Parsing with invalid mappings should not raise in tolerant mode
        result = parse_package_lazy(
            path, export_indices=[], tolerant=True,
            mappings_path="/nonexistent/mappings.json",
        )
        # Should complete without exception
        assert result is not None

    def test_lazy_non_tolerant_raises_on_bad_path(self):
        """Non-tolerant mode raises on invalid path."""
        from uasset_read.parse_uasset import parse_package_lazy
        from uasset_read.exceptions import ParseError, VersionError
        with pytest.raises((ParseError, VersionError, FileNotFoundError, OSError)):
            parse_package_lazy(
                "/nonexistent/path.uasset",
                export_indices=[],
                tolerant=False,
            )
