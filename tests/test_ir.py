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
        """所有 export 成功时 package 状态为 success。"""

        class MockExport:
            def __init__(self, status):
                self.parse_status = status

        exports = [
            MockExport("success"),
            MockExport("success"),
            MockExport("success"),
        ]
        result = MagicMock()
        result.is_success = True
        result.errors = []
        result.metadata = {}
        result.export_map = exports
        result.summary = MagicMock()
        result.summary.export_count = 3
        result.name_map = ["test"]
        result.import_map = {"test": "value"}
        result.graphs = None

        status = _result_status(result)
        assert status == "success"

    def test_opaque_export_makes_partial(self):
        """存在 opaque export 时 package 状态为 partial。"""

        class MockExport:
            def __init__(self, status):
                self.parse_status = status

        exports = [
            MockExport("success"),
            MockExport("opaque"),
            MockExport("success"),
        ]
        result = MagicMock()
        result.is_success = True
        result.errors = []
        result.metadata = {}
        result.export_map = exports
        result.summary = MagicMock()
        result.summary.export_count = 3
        result.name_map = ["test"]
        result.import_map = {"test": "value"}
        result.graphs = None

        status = _result_status(result)
        assert status == "partial"

    def test_partial_export_has_status_message(self):
        """#432: partial 包必须包含 status_message"""
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

        assert ir.status == "partial"
        assert ir.status_message is not None, "partial 包的 status_message 不应为 None"
        assert "opaque" in ir.status_message


# ============================================================================
# 动画 IR 数据模型（合并自 test_unit.py）
# ============================================================================

class TestAnimIRModels:
    def test_anim_sequence_ir_defaults(self):
        """AnimSequenceIR 默认值。"""
        ir = AnimSequenceIR()
        assert ir.target_skeleton is None
        assert ir.sequence_length == 0.0

    def test_anim_montage_ir_defaults(self):
        """AnimMontageIR 默认值。"""
        ir = AnimMontageIR()
        assert ir.rate_scale == 1.0
