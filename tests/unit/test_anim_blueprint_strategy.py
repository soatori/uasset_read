"""测试 AnimBlueprintGeneratedClass 序列化策略"""
from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    SerializationStrategy,
)


def test_anim_blueprint_strategy():
    """AnimBlueprintGeneratedClass 应该使用 TAGGED_PROPERTIES_ONLY"""
    strategy = get_serialization_strategy("AnimBlueprintGeneratedClass")
    assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY
