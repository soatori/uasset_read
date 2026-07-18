# tests/unit/test_opaque.py
"""Opaque 类相关单元测试（合并自 handlers / strategy / stub）"""
import pytest
from unittest.mock import MagicMock
from uasset_read.parsers.asset_types import register_asset_type_handlers
from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub
from uasset_read.parsers.class_registry import get_class_registry, reset_class_registry
from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    is_opaque_class,
    SerializationStrategy,
)


# ============================================================
# 测试数据
# ============================================================

# 所有应返回 partial_metadata 的 opaque class（16 个）
OPAQUE_CLASSES = [
    "FoliageType",
    "SkeletalMeshLODSettings",
    "AnimBoneCompressionSettings",
    "AnimCurveCompressionCodec",
    "PoseAsset",
    "SubsurfaceProfile",
    "AnimationDataModel",
    "Material",
    "MaterialInstanceConstant",
    "SkeletalMesh",
    "StaticMesh",
    "Texture2D",
    "TextureCube",
    "SoundWave",
    "SoundAttenuation",
    "StringTable",
]


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def _fresh_registry():
    """每个测试前重置 registry"""
    reset_class_registry()
    register_asset_type_handlers()
    yield
    reset_class_registry()


# ============================================================
# handler 注册路径和返回值测试
# ============================================================

@pytest.mark.parametrize("class_name", OPAQUE_CLASSES)
def test_opaque_handler_registered(class_name):
    """opaque class 应有注册的 handler"""
    registry = get_class_registry()
    handler = registry.find_handler(class_name)
    assert handler is not None, f"{class_name} 未注册 handler"


@pytest.mark.parametrize("class_name", OPAQUE_CLASSES)
def test_opaque_handler_returns_partial_metadata(class_name):
    """opaque handler 返回值应包含 parse_status: partial_metadata"""
    registry = get_class_registry()
    handler = registry.find_handler(class_name)
    assert handler is not None

    # 创建 mock export 和 archive
    export = MagicMock()
    export.object_name = f"Test{class_name}"
    archive = MagicMock()
    archive.tell.return_value = 0
    archive.total_size.return_value = 1024
    archive.read.return_value = b"\x00" * 256

    result = handler.parse(export, archive)
    assert result.success is True
    assert result.data["parse_status"] == "partial_metadata"
    assert result.data["sample_size"] == 256


# ============================================================
# class_serialization_strategy 策略测试
# ============================================================

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


# ============================================================
# opaque_stub 工厂函数测试
# ============================================================

def test_make_opaque_stub_returns_callable():
    """make_opaque_stub 应返回可调用对象"""
    fn = make_opaque_stub("TestClass")
    assert callable(fn)


def test_make_opaque_stub_read_sample():
    """返回的函数应读取最多 256 字节样本"""
    fn = make_opaque_stub("TestClass")
    archive = MagicMock()
    archive.tell.return_value = 100
    archive.total_size.return_value = 500
    archive.read.return_value = b"\x00" * 256
    result = fn(archive, [])
    assert result["raw_offset"] == 100
    assert result["sample_size"] == 256
    assert result["parse_status"] == "partial_metadata"


def test_make_opaque_stub_small_remainder():
    """剩余不足 256 字节时应读取全部剩余"""
    fn = make_opaque_stub("TestClass")
    archive = MagicMock()
    archive.tell.return_value = 480
    archive.total_size.return_value = 500
    archive.read.return_value = b"\x00" * 20
    result = fn(archive, [])
    assert result["sample_size"] == 20


def test_make_opaque_stub_empty_archive():
    """archive 为空时应返回零样本"""
    fn = make_opaque_stub("TestClass")
    archive = MagicMock()
    archive.tell.return_value = 100
    archive.total_size.return_value = 100
    archive.read.return_value = b""
    result = fn(archive, [])
    assert result["sample_size"] == 0
    assert result["parse_status"] == "partial_metadata"
