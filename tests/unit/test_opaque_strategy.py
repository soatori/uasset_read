"""class_serialization_strategy 中 FoliageType/SkeletalMeshLODSettings 策略测试"""
from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    is_opaque_class,
    SerializationStrategy,
)


def test_foliage_type_is_opaque():
    """FoliageType 应为 OPAQUE_CLASS_PAYLOAD"""
    assert is_opaque_class("FoliageType") is True
    assert get_serialization_strategy("FoliageType") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_skeletal_mesh_lod_settings_is_opaque():
    """SkeletalMeshLODSettings 应为 OPAQUE_CLASS_PAYLOAD"""
    assert is_opaque_class("SkeletalMeshLODSettings") is True
    assert get_serialization_strategy("SkeletalMeshLODSettings") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_unknown_class_defaults_to_tagged():
    """未知 class 应默认返回 TAGGED_PROPERTIES_ONLY"""
    assert get_serialization_strategy("UnknownClass") == SerializationStrategy.TAGGED_PROPERTIES_ONLY
