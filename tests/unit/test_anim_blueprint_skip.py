"""测试 AnimBlueprintGeneratedClass 不再被跳过"""
from uasset_read.parsers.class_specific_skip import SKIP_CLASS_NAMES


def test_anim_blueprint_generated_class_not_skipped():
    """AnimBlueprintGeneratedClass 应该从跳过列表中移除"""
    assert "AnimBlueprintGeneratedClass" not in SKIP_CLASS_NAMES


def test_anim_blueprint_extension_still_skipped():
    """AnimBlueprintExtension 应该在 class_serialization_strategy 的跳过列表中（自定义序列化）"""
    from uasset_read.parsers.class_serialization_strategy import _SKIP_CLASSES
    assert "AnimBlueprintExtension" in _SKIP_CLASSES
