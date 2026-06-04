"""tests/test_offset_range_diagnostic.py — OffsetRangeDiagnostic 数据模型测试。"""
import pytest

from uasset_read.models.diagnostics import OffsetRangeDiagnostic


class TestOffsetRangeDiagnostic:
    """OffsetRangeDiagnostic 数据模型单元测试。"""

    def test_default_instance(self):
        """默认实例化 — 所有字段使用默认值。"""
        diag = OffsetRangeDiagnostic()
        assert diag.kind == "offset_range_diagnostic"
        assert diag.asset_path == ""
        assert diag.asset_type == ""
        assert diag.module == ""
        assert diag.object_name == ""
        assert diag.export_index is None
        assert diag.import_index is None
        assert diag.field == ""
        assert diag.current_pos == 0
        assert diag.target_offset == 0
        assert diag.read_size == 0
        assert diag.file_size == 0
        assert diag.range_start is None
        assert diag.range_end is None
        assert diag.source == ""
        assert diag.error == ""
        assert diag.fallback_used is False
        assert diag.fallback_result == ""

    def test_custom_instance(self):
        """自定义实例化 — 传入所有字段。"""
        diag = OffsetRangeDiagnostic(
            kind="custom_kind",
            asset_path="/Game/Test",
            asset_type="Blueprint",
            module="linker",
            object_name="MyObject",
            export_index=3,
            import_index=7,
            field="serial_offset",
            current_pos=1024,
            target_offset=2048,
            read_size=512,
            file_size=4096,
            range_start=512,
            range_end=3000,
            source="PackageLinker",
            error="offset out of range",
            fallback_used=True,
            fallback_result="partial",
        )
        assert diag.kind == "custom_kind"
        assert diag.asset_path == "/Game/Test"
        assert diag.asset_type == "Blueprint"
        assert diag.module == "linker"
        assert diag.object_name == "MyObject"
        assert diag.export_index == 3
        assert diag.import_index == 7
        assert diag.field == "serial_offset"
        assert diag.current_pos == 1024
        assert diag.target_offset == 2048
        assert diag.read_size == 512
        assert diag.file_size == 4096
        assert diag.range_start == 512
        assert diag.range_end == 3000
        assert diag.source == "PackageLinker"
        assert diag.error == "offset out of range"
        assert diag.fallback_used is True
        assert diag.fallback_result == "partial"

    def test_to_dict_default(self):
        """to_dict() 默认实例 — 仅含 kind 和整数零值字段。"""
        diag = OffsetRangeDiagnostic()
        d = diag.to_dict()
        assert isinstance(d, dict)
        assert d["kind"] == "offset_range_diagnostic"
        # 整数字段始终输出（含 0）
        assert d["current_pos"] == 0
        assert d["target_offset"] == 0
        assert d["read_size"] == 0
        assert d["file_size"] == 0
        # 空字符串字段不输出
        assert "asset_path" not in d
        assert "module" not in d
        assert "error" not in d
        # None 字段不输出
        assert "export_index" not in d
        assert "range_start" not in d
        # False 布尔不输出
        assert "fallback_used" not in d

    def test_to_dict_full(self):
        """to_dict() 完整实例 — 所有字段均输出。"""
        diag = OffsetRangeDiagnostic(
            asset_path="/Game/Test.uasset",
            asset_type="SkeletalMesh",
            module="property",
            object_name="SK_Mannequin",
            export_index=0,
            import_index=None,
            field="serial_offset",
            current_pos=512,
            target_offset=1024,
            read_size=256,
            file_size=8192,
            range_start=0,
            range_end=1024,
            source="PropertyParser",
            error="read past end of export data",
            fallback_used=True,
            fallback_result="failed",
        )
        d = diag.to_dict()
        assert d["kind"] == "offset_range_diagnostic"
        assert d["asset_path"] == "/Game/Test.uasset"
        assert d["asset_type"] == "SkeletalMesh"
        assert d["module"] == "property"
        assert d["object_name"] == "SK_Mannequin"
        assert d["export_index"] == 0
        assert "import_index" not in d  # None 不输出
        assert d["field"] == "serial_offset"
        assert d["current_pos"] == 512
        assert d["target_offset"] == 1024
        assert d["read_size"] == 256
        assert d["file_size"] == 8192
        assert d["range_start"] == 0
        assert d["range_end"] == 1024
        assert d["source"] == "PropertyParser"
        assert d["error"] == "read past end of export data"
        assert d["fallback_used"] is True
        assert d["fallback_result"] == "failed"

    def test_to_dict_json_serializable(self):
        """to_dict() 输出可被 json.dumps 序列化。"""
        import json
        diag = OffsetRangeDiagnostic(
            asset_path="/Game/Test",
            module="kismet",
            field="CodeOffset",
            current_pos=100,
            target_offset=200,
            read_size=50,
            file_size=4000,
            fallback_used=True,
            fallback_result="success",
        )
        d = diag.to_dict()
        # 不应抛出异常
        serialized = json.dumps(d, ensure_ascii=False)
        assert isinstance(serialized, str)
        assert "offset_range_diagnostic" in serialized

    def test_to_dict_zero_export_index(self):
        """export_index=0 应输出（非 None）。"""
        diag = OffsetRangeDiagnostic(export_index=0)
        d = diag.to_dict()
        assert d["export_index"] == 0

    def test_to_dict_none_export_index(self):
        """export_index=None 不应输出。"""
        diag = OffsetRangeDiagnostic(export_index=None)
        d = diag.to_dict()
        assert "export_index" not in d

    def test_to_dict_zero_range_boundaries(self):
        """range_start=0 应输出（非 None）。"""
        diag = OffsetRangeDiagnostic(range_start=0, range_end=0)
        d = diag.to_dict()
        assert d["range_start"] == 0
        assert d["range_end"] == 0

    def test_module_values(self):
        """验证各 module 值均可正确设置和输出。"""
        for mod in ("linker", "property", "graph", "pin", "kismet", "pak", "iostore"):
            diag = OffsetRangeDiagnostic(module=mod)
            d = diag.to_dict()
            assert d["module"] == mod

    def test_field_values(self):
        """验证各 field 值均可正确设置和输出。"""
        for fld in ("serial_offset", "script_serial_offset", "ValueEndOffset", "CodeOffset", "LinkedTo"):
            diag = OffsetRangeDiagnostic(field=fld)
            d = diag.to_dict()
            assert d["field"] == fld

    def test_fallback_result_values(self):
        """验证 fallback_result 各取值。"""
        for result in ("failed", "partial", "success"):
            diag = OffsetRangeDiagnostic(fallback_result=result)
            d = diag.to_dict()
            assert d["fallback_result"] == result
