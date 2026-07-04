"""Handler 参数化测试 — 合并 anim blueprint/montage 重复测试"""
import pytest
from unittest.mock import MagicMock
from uasset_read.parsers.asset_types.anim_blueprint import AnimBlueprintHandler
from uasset_read.parsers.asset_types.anim_montage import AnimMontageHandler
from uasset_read.models.fallback import ExportParseStatus


HANDLER_CLASSES = [
    ("AnimBlueprintHandler", AnimBlueprintHandler),
    ("AnimMontageHandler", AnimMontageHandler),
]


@pytest.mark.parametrize("name,cls", HANDLER_CLASSES, ids=[h[0] for h in HANDLER_CLASSES])
def test_handler_exists(name, cls):
    """Handler 类应该存在"""
    assert cls is not None


@pytest.mark.parametrize("name,cls", HANDLER_CLASSES, ids=[h[0] for h in HANDLER_CLASSES])
def test_handler_has_handle_method(name, cls):
    """Handler 应该有 handle 方法"""
    handler = cls()
    assert hasattr(handler, "handle")


@pytest.mark.parametrize("name,cls", HANDLER_CLASSES, ids=[h[0] for h in HANDLER_CLASSES])
def test_handler_returns_parse_status(name, cls):
    """handle 方法应该返回 ParseStatus"""
    handler = cls()
    export = MagicMock()
    export.instance = MagicMock()
    export.instance.properties = {}
    context = MagicMock()
    result = handler.handle(export, context)
    assert isinstance(result, ExportParseStatus)
