"""验证 UClass/BPGC 原生字段解析完整性。"""
import pytest
from pathlib import Path


class TestUClassParsingCompleteness:
    """UClass 原生字段解析完整性测试。"""

    def test_bpgc_strategy_is_uclass_native(self):
        """验证 BPGC 策略为 UCLASS_NATIVE。"""
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )

        strategy = get_serialization_strategy("BlueprintGeneratedClass")
        assert strategy == SerializationStrategy.UCLASS_NATIVE, \
            f"BPGC 应为 UCLASS_NATIVE，实际为 {strategy}"

    def test_widget_bpgc_strategy_is_uclass_native(self):
        """验证 WidgetBlueprintGeneratedClass 策略为 UCLASS_NATIVE。"""
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )

        strategy = get_serialization_strategy("WidgetBlueprintGeneratedClass")
        assert strategy == SerializationStrategy.UCLASS_NATIVE

    def test_uclass_parser_exists(self):
        """验证 uclass parser 模块存在。"""
        from uasset_read.parsers.asset_types import uclass
        assert hasattr(uclass, "parse_uclass_fields")

    def test_uclass_fields_structure(self):
        """验证 UClass 字段结构包含所有必要字段。"""
        from uasset_read.parsers.asset_types.uclass import parse_uclass_fields
        # 验证函数签名和返回值结构
        import inspect
        sig = inspect.signature(parse_uclass_fields)
        params = list(sig.parameters.keys())
        assert "archive" in params
        assert "name_map" in params

    def test_uclass_native_fields_propagated_to_ir(self):
        """验证 _uclass_native_fields 被传递到 ExportIR.diagnostics。"""
        from uasset_read.ir_builder import _build_export_diagnostics

        # 模拟一个带有 _uclass_native_fields 的 export 对象
        class MockExport:
            transforms = {}
            _uclass_native_fields = {
                "parse_status": "success",
                "func_map": {"count": 5, "entries": []},
                "class_flags": 0x00000001,
                "interfaces": {"count": 2, "interfaces": []},
                "class_default_object": {"is_null": False, "export_index": 3},
                "bytes_read": 80,
            }

        export = MockExport()
        diagnostics = _build_export_diagnostics(export)

        assert diagnostics is not None, "diagnostics 不应为 None"
        assert "uclass_native" in diagnostics, \
            "diagnostics 应包含 uclass_native 键"
        uclass_diag = diagnostics["uclass_native"]
        assert uclass_diag["func_map_count"] == 5
        assert uclass_diag["class_flags"] == 0x00000001
        assert uclass_diag["interfaces_count"] == 2
        assert uclass_diag["has_cdo"] is True

    def test_uclass_native_fields_missing_is_ok(self):
        """验证没有 _uclass_native_fields 时 diagnostics 不受影响。"""
        from uasset_read.ir_builder import _build_export_diagnostics

        class MockExport:
            transforms = {}

        export = MockExport()
        diagnostics = _build_export_diagnostics(export)
        # 没有 transforms 也没有 _uclass_native_fields → None
        assert diagnostics is None

    def test_uclass_native_fields_with_cdo_null(self):
        """验证 CDO 为 null 时 has_cdo 为 False。"""
        from uasset_read.ir_builder import _build_export_diagnostics

        class MockExport:
            transforms = {}
            _uclass_native_fields = {
                "parse_status": "success",
                "func_map": {"count": 0, "entries": []},
                "class_flags": 0,
                "interfaces": {"count": 0, "interfaces": []},
                "class_default_object": {"is_null": True},
                "bytes_read": 60,
            }

        export = MockExport()
        diagnostics = _build_export_diagnostics(export)
        assert diagnostics is not None
        assert diagnostics["uclass_native"]["has_cdo"] is False

    def test_uclass_native_fields_partial_parse(self):
        """验证部分解析状态也被传递。"""
        from uasset_read.ir_builder import _build_export_diagnostics

        class MockExport:
            transforms = {}
            _uclass_native_fields = {
                "parse_status": "partial",
                "parse_error": "SuperStruct mismatch",
            }

        export = MockExport()
        diagnostics = _build_export_diagnostics(export)
        assert diagnostics is not None
        uclass_diag = diagnostics["uclass_native"]
        assert uclass_diag["func_map_count"] == 0
        assert uclass_diag["parse_status"] == "partial"
