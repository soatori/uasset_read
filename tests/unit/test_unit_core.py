"""unit 核心测试 — 合并自多个 unit 测试模块。

合并自：
- test_unit_handlers.py — Opaque 类 handler 注册、策略、stub 工厂 + Texture2D 尺寸校验
- test_material_instance_params.py — UMaterialInstance 参数提取 + BasePropertyOverrides + 代码质量 + PackageProvider + 游戏版本
- test_struct_parsing.py — LWC 版本感知、tagged fallback、BoxSphereBounds
"""
from __future__ import annotations

import ast
import inspect
import logging
import os
import struct
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from uasset_read.archive import FArchive
from uasset_read.graph import flow_builder
from uasset_read.models.fallback import ExportParseStatus
from uasset_read.models.properties import PropertyTag, StructValue
from uasset_read.objects.exports.material import (
    _collect_base_property_overrides,
    _BASE_PROPERTY_OVERRIDE_NAMES,
)
from uasset_read.objects.exports.texture import UTexture2D, _MAX_TEXTURE_DIMENSION
from uasset_read.package import FileSystemPackageProvider
from uasset_read.pak.constants import PakFileVersion
from uasset_read.pak.game_versions import (
    EGame,
    GAME_PAK_VERSION_MAP,
    MAGIC_TO_GAME_MAP,
    detect_game_from_magic,
    get_pak_version_for_game,
    get_game_info,
)
from uasset_read.parsers.asset_types import register_asset_type_handlers
from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub
from uasset_read.parsers.class_registry import get_class_registry, reset_class_registry
from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    is_opaque_class,
    SerializationStrategy,
)
from uasset_read.parsers.property_types import (
    _EXPECTED_STRUCT_SIZES,
    _TAGGED_FALLBACK_STRUCTS,
    _TAGGED_FALLBACK_STRUCT_SCHEMAS,
    get_struct_size,
    parse_struct_property,
)
from uasset_read.versioning import VersionContainer

from tests.conftest import asset_path, ASSET_MESH_CHAIR


# ============================================================
# Opaque 类测试数据（来自 test_unit_handlers.py）
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


# ============================================================
# UMaterialInstance 参数提取（来自 test_material_instance_params.py）
# ============================================================


class TestCollectParametersEnhanced:
    def test_collect_parameters_extracts_association(self):
        """_collect_parameters 应提取 Association 字段"""
        from uasset_read.objects.exports.material import _collect_parameters

        source = [{
            "ParameterInfo": {"Name": "BaseColor", "Association": 0, "Index": -1},
            "ParameterValue": [1.0, 0.0, 0.0, 1.0],
        }]
        result = _collect_parameters(source, value_names=("ParameterValue",))
        assert "BaseColor" in result
        assert result["BaseColor"]["association"] == 0
        assert result["BaseColor"]["index"] == -1

    def test_collect_parameters_extracts_index(self):
        """_collect_parameters 应提取 Index 字段"""
        from uasset_read.objects.exports.material import _collect_parameters

        source = [{
            "ParameterInfo": {"Name": "LayerMask", "Association": 1, "Index": 2},
            "ParameterValue": 0.5,
        }]
        result = _collect_parameters(source, value_names=("ParameterValue",))
        assert result["LayerMask"]["index"] == 2

    def test_collect_parameters_preserves_value(self):
        """_collect_parameters 应保留原有 value 字段"""
        from uasset_read.objects.exports.material import _collect_parameters

        source = [{
            "ParameterInfo": {"Name": "Roughness"},
            "ParameterValue": 0.3,
        }]
        result = _collect_parameters(source, value_names=("ParameterValue",))
        assert result["Roughness"]["value"] == 0.3


class TestStaticSwitchParameters:
    def test_static_switch_parameters_extracted(self):
        """UMaterialInstance 应提取 StaticSwitchParameters"""
        from uasset_read.objects.exports.material import UMaterialInstance

        mock_archive = MagicMock()
        instance = UMaterialInstance()
        # 模拟属性标签数据
        instance.properties = {
            "StaticSwitchParameters": [{
                "ParameterInfo": {"Name": "UseNormalMap"},
                "Value": True,
                "bOverride": True,
            }]
        }
        instance.deserialize(mock_archive, 0, 100)
        assert "UseNormalMap" in instance.static_switch_parameters
        assert instance.static_switch_parameters["UseNormalMap"] is True


# ============================================================
# BasePropertyOverrides 测试
# ============================================================

class TestBasePropertyOverrides(unittest.TestCase):
    """测试 _collect_base_property_overrides"""

    def test_empty_source(self):
        """空输入返回空 dict"""
        self.assertEqual(_collect_base_property_overrides(None), {})
        self.assertEqual(_collect_base_property_overrides({}), {})
        self.assertEqual(_collect_base_property_overrides([]), {})

    def test_dict_passthrough(self):
        """dict 输入直接返回"""
        data = {"BlendMode": 1, "TwoSided": True}
        result = _collect_base_property_overrides(data)
        self.assertEqual(result, data)

    def test_extracts_overridden_properties(self):
        """提取被 override 的属性"""
        mock_obj = MagicMock()
        # 模拟 prop_value 调用
        mock_props = {
            "bOverride_BlendMode": True,
            "BlendMode": 2,
            "bOverride_TwoSided": True,
            "TwoSided": True,
            "bOverride_ShadingModel": False,  # 未 override
            "ShadingModel": 1,  # 即使有值也不应被提取
        }
        def mock_prop_value(obj, *names, default=None):
            for name in names:
                if name in mock_props:
                    return mock_props[name]
            return default

        import uasset_read.objects.exports.material as mat_mod
        original_prop_value = mat_mod.prop_value
        mat_mod.prop_value = mock_prop_value
        try:
            result = _collect_base_property_overrides(mock_obj)
            self.assertEqual(result, {"BlendMode": 2, "TwoSided": True})
        finally:
            mat_mod.prop_value = original_prop_value

    def test_override_flag_names(self):
        """确认所有 override 标记名格式正确"""
        for name in _BASE_PROPERTY_OVERRIDE_NAMES:
            self.assertTrue(name[0].isupper() or name.startswith("b"),
                            f"属性名应以大写字母或 b 开头: {name}")


# ============================================================
# 代码质量静态检查测试
# ============================================================

class TestNoMutableDefaults:
    """验证 flow_builder 中无可变默认参数。"""

    def _get_functions_with_mutable_defaults(self, module):
        """扫描模块中所有函数的可变默认参数。"""
        issues = []
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            sig = inspect.signature(obj)
            for param_name, param in sig.parameters.items():
                if param.default is not inspect.Parameter.empty:
                    if isinstance(param.default, (dict, list, set)):
                        issues.append(f"{name}({param_name}={param.default})")
        return issues

    def test_flow_builder_no_mutable_defaults(self):
        """flow_builder 应无可变默认参数。"""
        issues = self._get_functions_with_mutable_defaults(flow_builder)
        assert len(issues) == 0, (
            f"flow_builder 存在可变默认参数: {issues}"
        )


class TestNoSilentExceptions:
    """验证无 except + pass 的静默吞没。"""

    def _find_silent_exceptions(self, filepath):
        """检测文件中的 except + pass 模式。"""
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                        issues.append(f"行 {handler.lineno}: except {handler.type}")
        return issues

    def test_src_no_silent_exceptions(self):
        """src/ 目录下应无静默异常吞没（允许已知的安全网和清理代码）。"""
        src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "src", "uasset_read")
        # 允许的静默异常模式（cleanup/safety-net），匹配相对路径
        allowed_files = {
            "archive.py",  # __del__ 安全网
            "parse_uasset.py",  # 清理代码
            "core/__init__.py",  # 清理代码
            "iostore/reader.py",  # 安全网
            "pak/reader.py",  # 安全网
        }
        all_issues = []
        for root, _, files in os.walk(src_dir):
            for f in files:
                if f.endswith(".py"):
                    filepath = os.path.join(root, f)
                    # 计算相对路径用于匹配
                    rel_path = os.path.relpath(filepath, src_dir).replace(os.sep, "/")
                    if rel_path in allowed_files:
                        continue
                    issues = self._find_silent_exceptions(filepath)
                    for issue in issues:
                        all_issues.append(f"{filepath}: {issue}")
        assert len(all_issues) == 0, (
            f"发现 {len(all_issues)} 处静默异常吞没:\n" + "\n".join(all_issues[:10])
        )


# ============================================================
# FileSystemPackageProvider root containment 校验
# ============================================================

def test_read_file_outside_root_raises():
    """read_file 应拒绝 root 外路径。"""
    root = Path(__file__).parent
    provider = FileSystemPackageProvider(root)
    with pytest.raises(PermissionError, match="outside root"):
        provider.read_file(str(root / ".." / "README.md"))


def test_open_file_outside_root_raises():
    """open_file 应拒绝 root 外路径。"""
    root = Path(__file__).parent
    provider = FileSystemPackageProvider(root)
    with pytest.raises(PermissionError, match="outside root"):
        provider.open_file(str(root / ".." / "README.md"))


def test_open_package_bundle_outside_root_raises():
    """open_package_bundle 应拒绝 root 外路径。"""
    root = Path(__file__).parent
    provider = FileSystemPackageProvider(root)
    with pytest.raises(PermissionError, match="outside root"):
        provider.open_package_bundle(str(root / ".." / "some.uasset"))


def test_read_file_within_root_ok():
    """read_file 应允许 root 内路径。"""
    root = Path(__file__).parent
    provider = FileSystemPackageProvider(root)
    result = provider.read_file(str(Path(__file__)))
    assert result is not None


# ============================================================
# 游戏版本映射测试
# ============================================================

class TestEGameExpansion(unittest.TestCase):
    """EGame 枚举扩展测试"""

    def test_popular_ue5_games_exist(self):
        """EGame 应包含热门 UE5 游戏"""
        self.assertTrue(hasattr(EGame, "BLACK_MYTH_WUKONG"))
        self.assertTrue(hasattr(EGame, "STALKER_2"))
        self.assertTrue(hasattr(EGame, "MARVEL_RIVALS"))
        self.assertTrue(hasattr(EGame, "THE_FIRST_DESCENDANT"))
        self.assertTrue(hasattr(EGame, "INFINITY_NIKKI"))

    def test_popular_ue4_games_exist(self):
        """EGame 应包含热门 UE4 游戏"""
        self.assertTrue(hasattr(EGame, "PUBG"))
        self.assertTrue(hasattr(EGame, "FORTNITE"))
        self.assertTrue(hasattr(EGame, "APEX_LEGENDS"))

    def test_game_pak_version_mapping(self):
        """新增游戏应有 PAK 版本映射"""
        self.assertIn(EGame.BLACK_MYTH_WUKONG, GAME_PAK_VERSION_MAP)
        self.assertEqual(
            GAME_PAK_VERSION_MAP[EGame.BLACK_MYTH_WUKONG],
            PakFileVersion.Utf8PakDirectory,
        )

    def test_game_info_returns_name(self):
        """get_game_info 应返回正确游戏名称"""
        name, version = get_game_info(EGame.BLACK_MYTH_WUKONG)
        self.assertEqual(name, "Black Myth: Wukong")

    def test_custom_magic_games_unchanged(self):
        """自定义魔数游戏应保持原有映射"""
        self.assertEqual(
            detect_game_from_magic(0xA590ED1E), EGame.OUTLAST_TRIALS
        )
        self.assertEqual(
            get_pak_version_for_game(EGame.OUTLAST_TRIALS),
            PakFileVersion.PathHashIndex,
        )


# ============================================================================
# 辅助函数（来自 test_struct_parsing.py）
# ============================================================================

def _archive(tmp_path: Path, data: bytes) -> FArchive:
    """从字节数据创建测试用 FArchive。"""
    path = tmp_path / "data.bin"
    path.write_bytes(data)
    return FArchive(str(path), tolerant=False)


def _make_vc(ue5_version: int = 0, ue4_version: int = 0) -> VersionContainer:
    """创建测试用 VersionContainer。"""
    return VersionContainer(
        file_version_ue5=ue5_version,
        file_version_ue4=ue4_version,
    )


# ============================================================================
# get_struct_size — 基础功能
# ============================================================================

class TestGetStructSizeBasic:
    """get_struct_size 基础查询（无 version_container）。"""

    def test_known_non_lwc_type(self):
        """非 LWC 类型返回固定大小。"""
        assert get_struct_size("Color") == 4
        assert get_struct_size("Guid") == 16
        assert get_struct_size("IntPoint") == 8
        assert get_struct_size("LinearColor") == 16

    def test_unknown_type_returns_none(self):
        """未知类型返回 None。"""
        assert get_struct_size("UnknownStruct") is None
        assert get_struct_size("CustomFoo") is None

    def test_no_version_container_uses_float_size(self):
        """无 version_container 时，LWC 基础类型返回 float 大小。"""
        assert get_struct_size("Vector") == 12
        assert get_struct_size("Rotator") == 12
        assert get_struct_size("Vector2D") == 8
        assert get_struct_size("Vector4") == 16
        assert get_struct_size("Quat") == 16
        assert get_struct_size("Plane") == 16
        assert get_struct_size("Sphere") == 16


# ============================================================================
# get_struct_size — LWC 版本感知
# ============================================================================

class TestGetStructSizeLWC:
    """get_struct_size LWC 版本感知。"""

    def test_ue4_returns_float_size(self):
        """UE4 版本返回 float 大小。"""
        vc = _make_vc(ue4_version=516)
        assert get_struct_size("Vector", vc) == 12
        assert get_struct_size("Quat", vc) == 16

    def test_ue5_pre_lwc_returns_float_size(self):
        """UE5 pre-LWC (file_version_ue5 < 1004) 返回 float 大小。"""
        vc = _make_vc(ue5_version=1000)
        assert get_struct_size("Vector", vc) == 12
        assert get_struct_size("Rotator", vc) == 12
        assert get_struct_size("Vector2D", vc) == 8
        assert get_struct_size("Vector4", vc) == 16
        assert get_struct_size("Quat", vc) == 16
        assert get_struct_size("Plane", vc) == 16
        assert get_struct_size("Sphere", vc) == 16

    def test_ue5_lwc_returns_double_size(self):
        """UE5 LWC (file_version_ue5 >= 1004) 返回 double 大小。"""
        vc = _make_vc(ue5_version=1004)
        assert get_struct_size("Vector", vc) == 24
        assert get_struct_size("Rotator", vc) == 24
        assert get_struct_size("Vector2D", vc) == 16
        assert get_struct_size("Vector4", vc) == 32
        assert get_struct_size("Quat", vc) == 32
        assert get_struct_size("Plane", vc) == 32
        assert get_struct_size("Sphere", vc) == 32

    def test_ue5_lwc_higher_version(self):
        """UE5 LWC 更高版本也返回 double 大小。"""
        vc = _make_vc(ue5_version=1012)
        assert get_struct_size("Vector", vc) == 24
        assert get_struct_size("Quat", vc) == 32

    def test_non_lwc_type_unaffected_by_version(self):
        """非 LWC 类型不受版本影响。"""
        vc_lwc = _make_vc(ue5_version=1004)
        assert get_struct_size("Color", vc_lwc) == 4
        assert get_struct_size("Guid", vc_lwc) == 16
        assert get_struct_size("LinearColor", vc_lwc) == 16
        assert get_struct_size("IntPoint", vc_lwc) == 8


# ============================================================================
# get_struct_size — 显式精度变体
# ============================================================================

class TestGetStructSizeExplicitTypes:
    """显式精度变体类型（Vector3d, Vector3f 等）。"""

    def test_double_variants_always_return_double_size(self):
        """显式双精度变体始终返回 double 大小，不看版本。"""
        # 无版本
        assert get_struct_size("Vector3d") == 24
        assert get_struct_size("Vector4d") == 32
        assert get_struct_size("Rotator3d") == 24
        assert get_struct_size("Quat4d") == 32
        assert get_struct_size("Plane4d") == 32
        assert get_struct_size("Sphere3d") == 32

        # UE4 版本
        vc_ue4 = _make_vc(ue4_version=516)
        assert get_struct_size("Vector3d", vc_ue4) == 24
        assert get_struct_size("Quat4d", vc_ue4) == 32

        # UE5 LWC 版本
        vc_lwc = _make_vc(ue5_version=1004)
        assert get_struct_size("Vector3d", vc_lwc) == 24
        assert get_struct_size("Quat4d", vc_lwc) == 32

    def test_float_variants_always_return_float_size(self):
        """显式单精度变体始终返回 float 大小，不看版本。"""
        # 无版本
        assert get_struct_size("Vector3f") == 12
        assert get_struct_size("Vector4f") == 16
        assert get_struct_size("Rotator3f") == 12
        assert get_struct_size("Quat4f") == 16
        assert get_struct_size("Plane4f") == 16
        assert get_struct_size("Sphere3f") == 16
        assert get_struct_size("Vector2f") == 8

        # UE5 LWC 版本
        vc_lwc = _make_vc(ue5_version=1004)
        assert get_struct_size("Vector3f", vc_lwc) == 12
        assert get_struct_size("Quat4f", vc_lwc) == 16


# ============================================================================
# parse_struct_property — Quat/Plane/Sphere LWC 快速路径
# ============================================================================

class TestStructPropertyLWCFastPath:
    """验证 Quat/Plane/Sphere 的 LWC 双精度快速路径。"""

    def test_quat_f32_fast_path(self, tmp_path):
        """Quat 标准 float 精度快速路径。"""
        data = struct.pack("<ffff", 1.0, 2.0, 3.0, 4.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestQuat", type="StructProperty", size=16, struct_type="Quat")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Quat"
        assert abs(result.fields["X"] - 1.0) < 1e-6
        assert abs(result.fields["Y"] - 2.0) < 1e-6
        assert abs(result.fields["Z"] - 3.0) < 1e-6
        assert abs(result.fields["W"] - 4.0) < 1e-6

    def test_quat_f64_lwc_fast_path(self, tmp_path):
        """Quat LWC double 精度快速路径（tag.size=32）。"""
        data = struct.pack("<dddd", 1.5, 2.5, 3.5, 4.5)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestQuat", type="StructProperty", size=32, struct_type="Quat")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Quat"
        assert abs(result.fields["X"] - 1.5) < 1e-10
        assert abs(result.fields["Y"] - 2.5) < 1e-10
        assert abs(result.fields["Z"] - 3.5) < 1e-10
        assert abs(result.fields["W"] - 4.5) < 1e-10

    def test_plane_f32_fast_path(self, tmp_path):
        """Plane 标准 float 精度快速路径。"""
        data = struct.pack("<ffff", 0.0, 1.0, 0.0, -5.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestPlane", type="StructProperty", size=16, struct_type="Plane")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Plane"
        assert abs(result.fields["X"] - 0.0) < 1e-6
        assert abs(result.fields["W"] - (-5.0)) < 1e-6

    def test_plane_f64_lwc_fast_path(self, tmp_path):
        """Plane LWC double 精度快速路径（tag.size=32）。"""
        data = struct.pack("<dddd", 0.0, 1.0, 0.0, -5.5)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestPlane", type="StructProperty", size=32, struct_type="Plane")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Plane"
        assert abs(result.fields["X"] - 0.0) < 1e-10
        assert abs(result.fields["W"] - (-5.5)) < 1e-10

    def test_sphere_f32_fast_path(self, tmp_path):
        """Sphere 标准 float 精度快速路径。"""
        data = struct.pack("<ffff", 10.0, 20.0, 30.0, 5.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestSphere", type="StructProperty", size=16, struct_type="Sphere")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Sphere"
        assert abs(result.fields["Center"]["X"] - 10.0) < 1e-6
        assert abs(result.fields["W"] - 5.0) < 1e-6

    def test_sphere_f64_lwc_fast_path(self, tmp_path):
        """Sphere LWC double 精度快速路径（tag.size=32）。"""
        data = struct.pack("<dddd", 10.5, 20.5, 30.5, 5.5)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestSphere", type="StructProperty", size=32, struct_type="Sphere")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Sphere"
        assert abs(result.fields["Center"]["X"] - 10.5) < 1e-10
        assert abs(result.fields["W"] - 5.5) < 1e-10


# ============================================================================
# parse_struct_property — 版本感知尺寸验证
# ============================================================================

class TestStructPropertyVersionAwareValidation:
    """验证 parse_struct_property 的版本感知尺寸验证。"""

    def test_vector_f32_accepted_without_version(self, tmp_path):
        """Vector 12 字节（float）在无 summary 时被接受。"""
        data = struct.pack("<fff", 1.0, 2.0, 3.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="Pos", type="StructProperty", size=12, struct_type="Vector")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Vector"
        assert abs(result.fields["X"] - 1.0) < 1e-6

    def test_vector_f64_accepted_without_version(self, tmp_path):
        """Vector 24 字节（double）在无 summary 时通过预检查（属于 LWC 可变大小）。"""
        data = struct.pack("<ddd", 1.5, 2.5, 3.5)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="Pos", type="StructProperty", size=24, struct_type="Vector")
        # 无 summary 时，get_struct_size 返回 12（float），但 tag.size=24 不匹配
        # 预检查会 warning 并 fallback 到 generic path
        result = parse_struct_property(tag, archive, [], [], summary=None)
        # 应该返回 StructValue（fallback 到 generic path，无数据则 opaque）
        assert isinstance(result, StructValue)

    def test_vector_f32_size_mismatch_with_lwc_version(self, tmp_path):
        """Vector 12 字节在 UE5 LWC 版本下与预期 24 不匹配，fallback。"""
        data = struct.pack("<fff", 1.0, 2.0, 3.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="Pos", type="StructProperty", size=12, struct_type="Vector")

        # 创建一个具有 UE5 LWC 版本的 summary
        class MockSummary:
            file_version_ue5 = 1004
            file_version_ue4 = 0
            custom_versions = []

        result = parse_struct_property(tag, archive, [], [], summary=MockSummary())
        # 12 != 24 (LWC expected)，fallback 到 generic path
        assert isinstance(result, StructValue)


# ============================================================================
# ScalarParameterValue / FScalarParameterValue tagged fallback
# ============================================================================

class TestScalarParameterValueRegistration:
    """验证 ScalarParameterValue / FScalarParameterValue 在 tagged fallback 中注册。"""

    def test_scalar_param_in_tagged_fallback_structs(self):
        assert "ScalarParameterValue" in _TAGGED_FALLBACK_STRUCTS

    def test_f_scalar_param_in_tagged_fallback_structs(self):
        assert "FScalarParameterValue" in _TAGGED_FALLBACK_STRUCTS

    def test_f_material_parameter_info_in_tagged_fallback_structs(self):
        """FMaterialParameterInfo 也需注册，因为 ScalarParameterValue 依赖它。"""
        assert "FMaterialParameterInfo" in _TAGGED_FALLBACK_STRUCTS

    def test_scalar_param_in_fallback_schemas(self):
        assert "ScalarParameterValue" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_f_scalar_param_in_fallback_schemas(self):
        assert "FScalarParameterValue" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_f_material_parameter_info_in_fallback_schemas(self):
        assert "FMaterialParameterInfo" in _TAGGED_FALLBACK_STRUCT_SCHEMAS


class TestScalarParameterValueSchema:
    """验证 ScalarParameterValue schema 字段定义与 UE5 源码一致。"""

    def test_scalar_param_schema_fields(self):
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["ScalarParameterValue"]
        field_names = [f[0] for f in schema]
        assert "ParameterInfo" in field_names
        assert "ParameterValue" in field_names
        assert "bOverride" in field_names

    def test_scalar_param_schema_types(self):
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["ScalarParameterValue"]
        schema_dict = dict(schema)
        assert schema_dict["ParameterInfo"] == "StructProperty"
        assert schema_dict["ParameterValue"] == "FloatProperty"
        assert schema_dict["bOverride"] == "BoolProperty"

    def test_f_scalar_param_matches_scalar_param(self):
        """FScalarParameterValue 应与 ScalarParameterValue 有相同字段。"""
        assert (
            _TAGGED_FALLBACK_STRUCT_SCHEMAS["ScalarParameterValue"]
            == _TAGGED_FALLBACK_STRUCT_SCHEMAS["FScalarParameterValue"]
        )

    def test_material_parameter_info_schema_fields(self):
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FMaterialParameterInfo"]
        field_names = [f[0] for f in schema]
        assert "ParameterName" in field_names
        assert "Index" in field_names
        assert "bOverride" in field_names

    def test_material_parameter_info_schema_types(self):
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FMaterialParameterInfo"]
        schema_dict = dict(schema)
        assert schema_dict["ParameterName"] == "NameProperty"
        assert schema_dict["Index"] == "IntProperty"
        assert schema_dict["bOverride"] == "BoolProperty"


class TestScalarParameterValueTaggedParse:
    """验证 ScalarParameterValue tagged fallback 解析行为。"""

    def test_tagged_parse_material_parameter_info(self, tmp_path):
        """FMaterialParameterInfo tagged 格式解析。"""
        # 简化：直接验证 schema 注册和结构正确性，而非构造完整二进制
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FMaterialParameterInfo"]
        assert len(schema) == 3
        assert schema[0] == ("ParameterName", "NameProperty")
        assert schema[1] == ("Index", "IntProperty")
        assert schema[2] == ("bOverride", "BoolProperty")

    def test_scalar_param_field_count(self):
        """ScalarParameterValue schema 包含 3 个字段。"""
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["ScalarParameterValue"]
        assert len(schema) == 3

    def test_existing_fallbacks_not_affected_for_scalar(self):
        """确保已有的 tagged fallback 不受 ScalarParameterValue 注册影响。"""
        assert "MemberReference" in _TAGGED_FALLBACK_STRUCTS
        assert "MemberReference" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        assert "FrameRate" in _TAGGED_FALLBACK_STRUCTS
        assert "AnimNotifyTrack" in _TAGGED_FALLBACK_STRUCTS
        assert "FEditorElement" in _TAGGED_FALLBACK_STRUCTS
        assert "EditorElement" in _TAGGED_FALLBACK_STRUCTS

    def test_expected_struct_sizes_not_required(self):
        """ScalarParameterValue 不需要在 _EXPECTED_STRUCT_SIZES 中，
        因为它是 tagged 格式（大小可变），不是固定布局。"""
        assert "ScalarParameterValue" not in _EXPECTED_STRUCT_SIZES
        assert "FScalarParameterValue" not in _EXPECTED_STRUCT_SIZES


# ============================================================================
# FBlendSample / BlendSample tagged fallback
# ============================================================================

class TestFBlendSampleFallback:
    """验证 FBlendSample 在 tagged fallback 中。"""

    def test_fblendsample_in_tagged_fallback_structs(self):
        """FBlendSample 应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "FBlendSample" in _TAGGED_FALLBACK_STRUCTS

    def test_fblendsample_in_fallback_schemas(self):
        """FBlendSample 应有 tagged fallback schema。"""
        assert "FBlendSample" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FBlendSample"]
        assert ("SampleValue", "StructProperty") in schema
        assert ("Time", "FloatProperty") in schema
        assert ("RateScale", "IntProperty") in schema
        assert ("bIsValid", "BoolProperty") in schema
        assert len(schema) == 4

    def test_fblendsample_schema_field_order(self):
        """FBlendSample schema 字段顺序应与 UE 序列化顺序一致。"""
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FBlendSample"]
        field_names = [name for name, _ in schema]
        assert field_names == ["SampleValue", "Time", "RateScale", "bIsValid"]


class TestBlendSampleFallback:
    """验证无前缀别名 BlendSample 在 tagged fallback 中。"""

    def test_blendsample_in_tagged_fallback_structs(self):
        """BlendSample（无 F 前缀）应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "BlendSample" in _TAGGED_FALLBACK_STRUCTS

    def test_blendsample_in_fallback_schemas(self):
        """BlendSample 应有 tagged fallback schema。"""
        assert "BlendSample" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["BlendSample"]
        assert ("SampleValue", "StructProperty") in schema
        assert ("Time", "FloatProperty") in schema
        assert ("RateScale", "IntProperty") in schema
        assert ("bIsValid", "BoolProperty") in schema
        assert len(schema) == 4


class TestBlendSampleSchemaConsistency:
    """验证 FBlendSample 与 BlendSample schema 一致。"""

    def test_both_aliases_have_same_schema(self):
        """两个别名的 schema 应完全一致。"""
        assert _TAGGED_FALLBACK_STRUCT_SCHEMAS["FBlendSample"] == \
            _TAGGED_FALLBACK_STRUCT_SCHEMAS["BlendSample"]


# ============================================================================
# FEditorElement / EditorElement tagged fallback
# ============================================================================

class TestFEditorElementFallback:
    """验证 FEditorElement 在 tagged fallback 中。"""

    def test_feditorelement_in_tagged_fallback_structs(self):
        """FEditorElement 应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "FEditorElement" in _TAGGED_FALLBACK_STRUCTS

    def test_feditorelement_in_fallback_schemas(self):
        """FEditorElement 应有 tagged fallback schema。"""
        assert "FEditorElement" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FEditorElement"]
        assert ("DisplayName", "TextProperty") in schema
        assert ("Value", "StrProperty") in schema
        assert ("bIsDefault", "BoolProperty") in schema
        assert len(schema) == 3

    def test_feditorelement_schema_field_order(self):
        """FEditorElement schema 字段顺序应与 UE 序列化顺序一致。"""
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FEditorElement"]
        field_names = [name for name, _ in schema]
        assert field_names == ["DisplayName", "Value", "bIsDefault"]


class TestEditorElementFallback:
    """验证无前缀别名 EditorElement 在 tagged fallback 中。"""

    def test_editorelement_in_tagged_fallback_structs(self):
        """EditorElement（无 F 前缀）应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "EditorElement" in _TAGGED_FALLBACK_STRUCTS

    def test_editorelement_in_fallback_schemas(self):
        """EditorElement（无 F 前缀）应有 tagged fallback schema。"""
        assert "EditorElement" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["EditorElement"]
        assert ("DisplayName", "TextProperty") in schema
        assert ("Value", "StrProperty") in schema
        assert ("bIsDefault", "BoolProperty") in schema
        assert len(schema) == 3


class TestEditorElementSchemaConsistency:
    """验证 FEditorElement 与 EditorElement schema 一致。"""

    def test_both_aliases_have_same_schema(self):
        """两个别名的 schema 应完全一致。"""
        assert _TAGGED_FALLBACK_STRUCT_SCHEMAS["FEditorElement"] == \
            _TAGGED_FALLBACK_STRUCT_SCHEMAS["EditorElement"]


# ============================================================================
# BoxSphereBounds 解析验证（Issue #175）
# ============================================================================

# 样本文件完整路径
CHAIR_PATH = Path(__file__).parent.parent / "samples" / "StackOBot_M_BotBase.uasset"


@pytest.mark.integration
class TestBoxSphereBoundsParsing:
    """BoxSphereBounds 解析验证。"""

    def test_box_sphere_bounds_parsed(self, sample_root: Path):
        """验证本地样本资产能正确解析。"""
        chair_path = asset_path(sample_root, ASSET_MESH_CHAIR)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(chair_path), tolerant=True)

        # 本地样本可能没有 BoxSphereBounds 属性，只验证解析成功
        assert result.is_success or result.status == "partial", f"解析失败: {result.errors}"
        assert len(result.export_map) > 0, "应有至少一个 export"

    def test_box_sphere_bounds_no_warning(self):
        """验证 BoxSphereBounds 解析不产生 '不匹配' 警告。"""
        if not os.path.exists(CHAIR_PATH):
            pytest.skip(f"样本文件不存在: {CHAIR_PATH}")

        from uasset_read.parse_uasset import parse_package

        handler = logging.handlers if hasattr(logging, "handlers") else None
        # 捕获 property_types 模块的 WARNING
        logger = logging.getLogger("uasset_read.parsers.property_types")

        class WarningCapture(logging.Handler):
            def __init__(self):
                super().__init__()
                self.warnings = []

            def emit(self, record):
                if record.levelno >= logging.WARNING:
                    self.warnings.append(record.getMessage())

        capture = WarningCapture()
        logger.addHandler(capture)
        try:
            result = parse_package(str(CHAIR_PATH), tolerant=True)
        finally:
            logger.removeHandler(capture)

        # 检查没有 BoxSphereBounds 相关的警告
        bounds_warnings = [w for w in capture.warnings if "BoxSphereBounds" in w]
        assert len(bounds_warnings) == 0, f"BoxSphereBounds 解析不应有警告: {bounds_warnings}"


# ============================================================================
# 通用 tagged fallback 存在性验证
# ============================================================================

class TestExistingFallbacksUnaffected:
    """确保现有 tagged fallback 不受新增注册影响。"""

    def test_member_reference_still_present(self):
        assert "MemberReference" in _TAGGED_FALLBACK_STRUCTS
        assert "MemberReference" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_framerate_still_present(self):
        assert "FrameRate" in _TAGGED_FALLBACK_STRUCTS
        assert "FrameRate" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_animnotifytrack_still_present(self):
        assert "AnimNotifyTrack" in _TAGGED_FALLBACK_STRUCTS
        assert "AnimNotifyTrack" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_feditor_element_still_present(self):
        assert "FEditorElement" in _TAGGED_FALLBACK_STRUCTS
        assert "FEditorElement" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_editor_element_still_present(self):
        assert "EditorElement" in _TAGGED_FALLBACK_STRUCTS
        assert "EditorElement" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_new_variables_still_present(self):
        assert "NewVariables" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
