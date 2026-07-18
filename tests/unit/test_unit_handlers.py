"""unit 处理器测试 — 合并自 test_opaque / test_texture2d_bounds。

验证：
1. Opaque 类相关（handler 注册、策略、stub 工厂）
2. Texture2D PlatformData 覆盖后的尺寸范围校验
"""
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
from uasset_read.objects.exports.texture import UTexture2D, _MAX_TEXTURE_DIMENSION


# ============================================================
# Opaque 类测试数据
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
# Opaque Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def _fresh_registry():
    """每个测试前重置 registry"""
    reset_class_registry()
    register_asset_type_handlers()
    yield
    reset_class_registry()


# ============================================================
# Opaque handler 注册路径和返回值测试
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


# ============================================================
# Texture2D 辅助函数
# ============================================================

def _make_texture(**props) -> UTexture2D:
    """构造带指定 properties 的 UTexture2D 实例"""
    tex = UTexture2D(name="TestTexture")
    for k, v in props.items():
        tex.set_property(k, v)
    return tex


def _make_archive() -> MagicMock:
    """构造最小 mock archive"""
    archive = MagicMock()
    archive.tell.return_value = 0
    archive.total_size.return_value = 1024
    return archive


# ============================================================
# Texture2D PlatformData 尺寸范围校验测试 (#403)
# ============================================================

class TestPlatformDataBounds:
    """PlatformData 覆盖尺寸后重新校验"""

    def test_platformdata_negative_sizex_clamped(self):
        """PlatformData 中 SizeX 为负值时应置为 0"""
        tex = _make_texture(
            PlatformData={"SizeX": -100, "SizeY": 256, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 0
        assert tex.size_y == 256

    def test_platformdata_negative_sizey_clamped(self):
        """PlatformData 中 SizeY 为负值时应置为 0"""
        tex = _make_texture(
            PlatformData={"SizeX": 256, "SizeY": -50, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 256
        assert tex.size_y == 0

    def test_platformdata_oversized_sizex_clamped(self):
        """PlatformData 中 SizeX 超过上限时应置为 0"""
        tex = _make_texture(
            PlatformData={"SizeX": _MAX_TEXTURE_DIMENSION + 1, "SizeY": 128, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 0
        assert tex.size_y == 128

    def test_platformdata_oversized_sizey_clamped(self):
        """PlatformData 中 SizeY 超过上限时应置为 0"""
        tex = _make_texture(
            PlatformData={"SizeX": 64, "SizeY": _MAX_TEXTURE_DIMENSION + 999, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 64
        assert tex.size_y == 0

    def test_platformdata_both_invalid_clamped(self):
        """PlatformData 中 SizeX/SizeY 均非法时均置为 0"""
        tex = _make_texture(
            PlatformData={"SizeX": -1, "SizeY": _MAX_TEXTURE_DIMENSION + 1, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 0
        assert tex.size_y == 0

    def test_platformdata_valid_values_preserved(self):
        """合法的 PlatformData 尺寸不应被篡改"""
        tex = _make_texture(
            PlatformData={"SizeX": 1024, "SizeY": 2048, "PixelFormat": 2, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 1024
        assert tex.size_y == 2048

    def test_imported_invalid_overridden_by_valid_platformdata(self):
        """初始 SizeX 非法但 PlatformData 合法时，PlatformData 覆盖后保留合法值"""
        tex = _make_texture(
            SizeX=99999, SizeY=99999,
            PlatformData={"SizeX": 512, "SizeY": 512, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        # 初始校验将 99999 置为 0，PlatformData 再覆盖为 512
        assert tex.size_x == 512
        assert tex.size_y == 512

    def test_imported_valid_overridden_by_invalid_platformdata(self):
        """初始 SizeX 合法但 PlatformData 非法时，PlatformData 覆盖后应置为 0"""
        tex = _make_texture(
            SizeX=256, SizeY=256,
            PlatformData={"SizeX": -10, "SizeY": _MAX_TEXTURE_DIMENSION + 1, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 0
        assert tex.size_y == 0

    def test_no_platformdata_keeps_imported_bounds(self):
        """无 PlatformData 时，初始校验结果应保留"""
        tex = _make_texture(SizeX=200, SizeY=300)
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 200
        assert tex.size_y == 300

    def test_zero_boundary_values(self):
        """边界值 0 和 _MAX_TEXTURE_DIMENSION 应被接受"""
        tex = _make_texture(
            PlatformData={"SizeX": 0, "SizeY": _MAX_TEXTURE_DIMENSION, "PixelFormat": 1, "Mips": []},
        )
        tex.deserialize(_make_archive(), offset=0, size=100)
        assert tex.size_x == 0
        assert tex.size_y == _MAX_TEXTURE_DIMENSION
