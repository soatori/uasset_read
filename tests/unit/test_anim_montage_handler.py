"""AnimMontage Handler 单元测试"""
import pytest
from unittest.mock import MagicMock
from uasset_read.parsers.asset_types.anim_montage import AnimMontageHandler
from uasset_read.models.ir import AnimMontageIR


class TestAnimMontageHandler:
    def test_handler_exists(self):
        """Handler 类应该存在"""
        assert AnimMontageHandler is not None

    def test_handler_has_handle_method(self):
        """Handler 应该有 handle 方法"""
        handler = AnimMontageHandler()
        assert hasattr(handler, "handle")

    def test_handler_returns_parse_status(self):
        """handle 方法应该返回 ParseStatus"""
        from uasset_read.models.fallback import ExportParseStatus
        handler = AnimMontageHandler()
        # Mock export 和 context
        export = MagicMock()
        export.instance = MagicMock()
        export.instance.properties = {}
        context = MagicMock()
        result = handler.handle(export, context)
        assert isinstance(result, ExportParseStatus)
