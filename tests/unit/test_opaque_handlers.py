# tests/unit/test_opaque_handlers.py
"""Opaque handler registration path and return value tests."""
import pytest
from unittest.mock import MagicMock
from uasset_read.parsers.class_registry import get_class_registry


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


@pytest.fixture(autouse=True)
def _fresh_registry():
    """Reset and re-bootstrap registry before each test."""
    from uasset_read.parsers.class_registry import reset_class_registry
    reset_class_registry()
    # get_class_registry() triggers deterministic bootstrap — no explicit
    # register_asset_type_handlers() call needed.
    get_class_registry()
    yield
    reset_class_registry()


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
