"""IR 模块合并测试。

合并自 test_ir_core.py、test_ir_utils.py。
保留 4 个关键用例：核心 IR 构建、工具函数。
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from uasset_read.ir_builder import (
    build_package_ir,
    _build_pin_ir,
    _result_status,
    _normalize_guid,
    _safe_int,
)
from uasset_read.models.ir import (
    PackageIR, ExportIR, PackageHeaderIR, GraphIR, NodeIR, PinIR,
    AnimSequenceIR, AnimMontageIR,
)


# === 辅助工厂 ===

def _make_mock_parse_result():
    """创建最小 Mock ParseResult。"""
    result = MagicMock()
    result.summary.package_name = "/Game/Test/BP_Test"
    result.summary.package_class = "BP_Test_C"
    result.summary.package_flags = 0
    result.summary.total_export_count = 1
    result.summary.total_import_count = 1
    result.name_map = ["BP_Test", "SomeName"]
    result.import_map = []
    result.export_map = []
    result.linker = None
    result.blueprint = None
    result.version_container = None
    result.errors = []
    result.warnings = []
    result.is_success = True
    return result


# === 4 个关键用例 ===

class TestBuildPackageIR:
    """IR 构建器核心测试。"""

    def test_build_minimal_result(self):
        """最小 ParseResult 应正确构建 PackageIR。"""
        result = _make_mock_parse_result()
        ir = build_package_ir(result)
        assert isinstance(ir, PackageIR)
        assert ir.header.package_name == "/Game/Test/BP_Test"
        assert ir.header.package_class == "BP_Test_C"
        assert ir.name_map == ("BP_Test", "SomeName")
        assert ir.exports == []
        assert ir.imports == []
        assert ir.linker is None


class TestPinIRStructuredFields:
    """Pin 结构化字段测试。"""

    def test_pin_structured_type_fields(self):
        """FEdGraphPinType 结构化字段正确提取。"""
        mock_pin = MagicMock()
        mock_pin.pin_name = "Value"
        mock_pin.pin_type = MagicMock()
        mock_pin.pin_type.pin_category = "struct"
        mock_pin.pin_type.pin_subcategory = ""
        mock_pin.pin_type.pin_subcategory_object_name = "/Script/Engine.Vector"
        mock_pin.pin_type.container_type = 1  # Array
        mock_pin.pin_type.is_reference = True
        mock_pin.pin_type.is_const = False
        mock_pin.pin_type.is_weak_pointer = False
        mock_pin.pin_type.is_uobject_wrapper = False
        mock_pin.pin_type.is_map_key = False
        mock_pin.pin_type.is_map_value = False
        mock_pin.linked_to_raw = []
        mock_pin.direction = 1  # Output
        mock_pin.default_value = None

        pin_ir = _build_pin_ir(mock_pin)
        assert pin_ir.pin_category == "struct"
        assert pin_ir.pin_subcategory_object_name == "/Script/Engine.Vector"
        assert pin_ir.container_type == "Array"
        assert pin_ir.is_reference is True
        assert pin_ir.is_const is False


class TestStatusModel:
    """状态模型推导测试。"""

    def test_all_exports_success(self):
        """所有 export 成功时 package 状态为 success；存在 opaque 时为 partial。"""
        class MockExport:
            def __init__(self, status):
                self.parse_status = status

        def _make_result(exports_list):
            r = MagicMock(); r.is_success = True; r.errors = []; r.metadata = {}
            r.export_map = exports_list; r.summary = MagicMock()
            r.summary.export_count = len(exports_list); r.name_map = ["test"]
            r.import_map = {}; r.graphs = None
            return r

        assert _result_status(_make_result([MockExport("success"), MockExport("success")])) == "success"
        assert _result_status(_make_result([MockExport("success"), MockExport("opaque")])) == "partial"

    def test_partial_export_has_status_message(self):
        """#432: partial 包必须包含 status_message；#431: EXPORT_PARTIAL 消息应包含 fallback_reason。"""
        from uasset_read.models.fallback import ExportParseStatus

        export = MagicMock()
        export.parse_status = ExportParseStatus.OPAQUE
        export.object_name = "TestExport"
        export.export_index = 0
        export.class_name = "None"
        export.is_function = False
        export.is_blueprint = False
        export.cooked_size = 0
        export.properties = {}

        result = MagicMock()
        result.package_name = "/Game/TestPackage"
        result.include_decompiled = False
        result.errors = []
        result.warnings = []
        result.decompiled_functions = []
        result.metadata = {}
        result.export_map = [export]

        ir = build_package_ir(result)

        assert ir.diagnostics_data.status == "partial"
        assert ir.diagnostics_data.status_message is not None, "partial 包的 status_message 不应为 None"
        assert "opaque" in ir.diagnostics_data.status_message

    def test_all_failed_exports_makes_failed(self):
        """全 failed->failed；混合/ skipped ->partial。"""
        class MockExport:
            def __init__(self, status):
                self.parse_status = status

        def _make_result(exports_list):
            r = MagicMock(); r.is_success = True; r.errors = []; r.metadata = {}
            r.export_map = exports_list; r.summary = MagicMock()
            r.summary.export_count = len(exports_list); r.name_map = ["test"]
            r.import_map = {}; r.graphs = None
            return r

        assert _result_status(_make_result([MockExport("failed"), MockExport("failed")])) == "failed"
        assert _result_status(_make_result([MockExport("success"), MockExport("failed")])) == "partial"
        assert _result_status(_make_result([MockExport("success"), MockExport("skipped")])) == "partial"

    def test_is_success_false_with_core_data(self):
        """is_success=False 有核心数据->partial；无核心数据->failed；errors->partial。"""
        def _make_result(**overrides):
            r = MagicMock(); r.is_success = True; r.errors = []; r.metadata = {}; r.export_map = []
            r.summary = MagicMock(); r.summary.export_count = 0
            r.name_map = ["test"]; r.import_map = {}; r.graphs = None
            for k, v in overrides.items(): setattr(r, k, v)
            return r

        assert _result_status(_make_result(is_success=False)) == "partial"
        assert _result_status(_make_result(is_success=False, summary=None, name_map=None, import_map=None)) == "failed"
        assert _result_status(_make_result(errors=["some error"])) == "partial"
        assert _result_status(_make_result(metadata={"lightweight_tolerant_parse": True})) == "partial"

    def test_export_partial_status_message_includes_reasons(self):
        """#431: EXPORT_PARTIAL 消息应包含 fallback_reason 示例。"""
        from uasset_read.models.fallback import ExportParseStatus

        export1 = MagicMock()
        export1.parse_status = ExportParseStatus.OPAQUE
        export1.fallback_reason = "opaque_payload:StaticMesh"
        export2 = MagicMock()
        export2.parse_status = ExportParseStatus.OPAQUE
        export2.fallback_reason = "opaque_payload:Texture2D"
        export3 = MagicMock()
        export3.parse_status = ExportParseStatus.SKIPPED
        export3.fallback_reason = "skip_unsupported:NiagaraSystem"

        result = MagicMock()
        result.package_name = "/Game/TestPackage"
        result.include_decompiled = False
        result.errors = []
        result.warnings = []
        result.decompiled_functions = []
        result.metadata = {}
        result.export_map = [export1, export2, export3]

        ir = build_package_ir(result)

        assert ir.diagnostics_data.status == "partial"
        assert ir.diagnostics_data.status_code == "EXPORT_PARTIAL"
        assert "opaque×2" in ir.diagnostics_data.status_message
        assert "skipped×1" in ir.diagnostics_data.status_message
        assert "StaticMesh" in ir.diagnostics_data.status_message


# ============================================================================
# 动画 IR 数据模型（合并自 test_unit.py）
# ============================================================================

class TestAnimIRModels:
    def test_anim_sequence_ir_defaults(self):
        """AnimSequenceIR/AnimMontageIR 默认值。"""
        assert AnimSequenceIR().target_skeleton is None
        assert AnimSequenceIR().sequence_length == 0.0
        assert AnimMontageIR().rate_scale == 1.0
