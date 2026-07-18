"""ObjectTypeRegistry 反射注册模式测试。

测试自动发现和手动注册机制。
"""
import pytest
from uasset_read.parsers.asset_types import (
    discover_handlers,
    get_handler,
    register_handler,
    AnimBlueprintHandler,
    AnimSequenceHandler,
    AnimMontageHandler,
)


class TestDiscoverHandlers:
    """测试自动发现处理器功能。"""

    def test_discover_handlers_returns_dict(self):
        """测试 discover_handlers 返回字典。"""
        handlers = discover_handlers()
        assert isinstance(handlers, dict)

    def test_discover_handlers_finds_anim_handlers(self):
        """测试自动发现动画处理器。"""
        handlers = discover_handlers()
        # 应该能发现 AnimBlueprintHandler, AnimSequenceHandler, AnimMontageHandler
        assert "AnimBlueprintGeneratedClass" in handlers
        assert "AnimSequence" in handlers
        assert "AnimMontage" in handlers

    def test_discover_handlers_returns_classes(self):
        """测试自动发现的处理器是类。"""
        handlers = discover_handlers()
        for export_type, handler in handlers.items():
            assert isinstance(handler, type), f"Handler for {export_type} should be a class"


class TestHandlerAttributes:
    """测试处理器包含必要属性。"""

    def test_anim_blueprint_handler_attributes(self):
        """测试 AnimBlueprintHandler 包含必要属性。"""
        assert hasattr(AnimBlueprintHandler, "export_type")
        assert hasattr(AnimBlueprintHandler, "priority")
        assert AnimBlueprintHandler.export_type == "AnimBlueprintGeneratedClass"
        assert AnimBlueprintHandler.priority == 100

    def test_anim_sequence_handler_attributes(self):
        """测试 AnimSequenceHandler 包含必要属性。"""
        assert hasattr(AnimSequenceHandler, "export_type")
        assert hasattr(AnimSequenceHandler, "priority")
        assert AnimSequenceHandler.export_type == "AnimSequence"
        assert AnimSequenceHandler.priority == 100

    def test_anim_montage_handler_attributes(self):
        """测试 AnimMontageHandler 包含必要属性。"""
        assert hasattr(AnimMontageHandler, "export_type")
        assert hasattr(AnimMontageHandler, "priority")
        assert AnimMontageHandler.export_type == "AnimMontage"
        assert AnimMontageHandler.priority == 100


class TestGetHandler:
    """测试获取处理器功能。"""

    def test_get_handler_anim_blueprint(self):
        """测试获取 AnimBlueprint 处理器。"""
        handler = get_handler("AnimBlueprintGeneratedClass")
        assert handler is not None
        assert handler == AnimBlueprintHandler

    def test_get_handler_anim_sequence(self):
        """测试获取 AnimSequence 处理器。"""
        handler = get_handler("AnimSequence")
        assert handler is not None
        assert handler == AnimSequenceHandler

    def test_get_handler_anim_montage(self):
        """测试获取 AnimMontage 处理器。"""
        handler = get_handler("AnimMontage")
        assert handler is not None
        assert handler == AnimMontageHandler

    def test_get_handler_not_found(self):
        """测试获取不存在的处理器返回 None。"""
        handler = get_handler("NonExistentType")
        assert handler is None


class TestRegisterHandler:
    """测试手动注册功能。"""

    def test_register_and_get_handler(self):
        """测试手动注册后可以获取。"""

        class MockHandler:
            export_type = "MockType"
            priority = 50

        register_handler("MockType", MockHandler)
        handler = get_handler("MockType")
        assert handler is not None
        assert handler == MockHandler

    def test_manual_register_overrides_auto_discover(self):
        """测试手动注册优先于自动发现。"""

        class CustomAnimHandler:
            export_type = "AnimSequence"
            priority = 200

        register_handler("AnimSequence", CustomAnimHandler)
        handler = get_handler("AnimSequence")
        assert handler == CustomAnimHandler


class TestIntegration:
    """集成测试。"""

    def test_all_discovered_handlers_have_required_attrs(self):
        """测试所有自动发现的处理器都有必要属性。"""
        handlers = discover_handlers()
        for export_type, handler_class in handlers.items():
            assert hasattr(handler_class, "export_type"), (
                f"Handler {handler_class.__name__} missing export_type"
            )
            assert hasattr(handler_class, "priority"), (
                f"Handler {handler_class.__name__} missing priority"
            )
            assert handler_class.export_type == export_type, (
                f"Handler {handler_class.__name__} export_type mismatch: "
                f"{handler_class.export_type} != {export_type}"
            )
