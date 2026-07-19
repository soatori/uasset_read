"""Unit 模块合并测试。

覆盖核心单元测试和动画相关：
1. Opaque handler 注册与策略
2. Texture2D 尺寸校验
3. LWC 版本感知 struct 大小
4. 动画 IR 数据模型
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from uasset_read.models.ir import (
    AnimSequenceIR,
    AnimMontageIR,
)
from uasset_read.objects.exports.texture import UTexture2D, _MAX_TEXTURE_DIMENSION
from uasset_read.parsers.asset_types import register_asset_type_handlers
from uasset_read.parsers.class_registry import get_class_registry, reset_class_registry
from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    SerializationStrategy,
)
from uasset_read.parsers.property_types import get_struct_size
from uasset_read.versioning import VersionContainer


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _make_vc(ue5_version: int = 0, ue4_version: int = 0) -> VersionContainer:
    return VersionContainer(file_version_ue5=ue5_version, file_version_ue4=ue4_version)

def _make_archive() -> MagicMock:
    archive = MagicMock()
    archive.tell.return_value = 0
    archive.total_size.return_value = 1024
    return archive

def _make_texture(**props) -> UTexture2D:
    tex = UTexture2D(name="TestTexture")
    for k, v in props.items():
        tex.set_property(k, v)
    return tex


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _fresh_registry():
    """每个测试前重置 registry。"""
    reset_class_registry()
    register_asset_type_handlers()
    yield
    reset_class_registry()


# ---------------------------------------------------------------------------
# 1. Opaque handler 注册与策略
# ---------------------------------------------------------------------------

class TestOpaqueHandlers:
    def test_handler_registered_foliage(self):
        """FoliageType 应有注册的 handler。"""
        registry = get_class_registry()
        handler = registry.find_handler("FoliageType")
        assert handler is not None

    def test_unknown_class_defaults_to_tagged(self):
        """未知 class 默认返回 TAGGED_PROPERTIES_ONLY。"""
        assert get_serialization_strategy("UnknownClass") == SerializationStrategy.TAGGED_PROPERTIES_ONLY


# ---------------------------------------------------------------------------
# 2. Texture2D 尺寸校验
# ---------------------------------------------------------------------------

class TestTexture2DBounds:
    def test_negative_sizex_clamped(self):
        """PlatformData SizeX 为负值时置为 0。"""
        tex = _make_texture(PlatformData={"SizeX": -100, "SizeY": 256, "PixelFormat": 1, "Mips": []})
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 0


# ---------------------------------------------------------------------------
# 3. LWC 版本感知 struct 大小
# ---------------------------------------------------------------------------

class TestStructSizeLWC:
    def test_ue4_returns_float_size(self):
        """UE4 版本返回 float 大小。"""
        vc = _make_vc(ue4_version=516)
        assert get_struct_size("Vector", vc) == 12

    def test_ue5_lwc_returns_double_size(self):
        """UE5 LWC (>= 1004) 返回 double 大小。"""
        vc = _make_vc(ue5_version=1004)
        assert get_struct_size("Vector", vc) == 24


# ---------------------------------------------------------------------------
# 4. 动画 IR 数据模型
# ---------------------------------------------------------------------------

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
