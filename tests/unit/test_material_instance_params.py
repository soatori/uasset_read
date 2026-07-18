"""UMaterialInstance 参数提取及 BasePropertyOverrides 测试（合并自 test_base_property_overrides）

合并来源：
  - test_base_property_overrides.py
  - test_quality_checks.py
  - test_package_provider.py
  - test_game_versions.py
"""
import ast
import inspect
import os
import pytest
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from uasset_read.objects.exports.material import (
    _collect_base_property_overrides,
    _BASE_PROPERTY_OVERRIDE_NAMES,
)
from uasset_read.graph import flow_builder
from uasset_read.package import FileSystemPackageProvider
from uasset_read.pak.game_versions import (
    EGame,
    GAME_PAK_VERSION_MAP,
    MAGIC_TO_GAME_MAP,
    detect_game_from_magic,
    get_pak_version_for_game,
    get_game_info,
)
from uasset_read.pak.constants import PakFileVersion


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
# BasePropertyOverrides 测试（原 test_base_property_overrides.py）
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
# 代码质量静态检查测试（原 test_quality_checks.py）
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
        src_dir = os.path.join(os.path.dirname(__file__), "..", "src", "uasset_read")
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
# FileSystemPackageProvider root containment 校验（原 test_package_provider.py）
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
# 游戏版本映射测试（原 test_game_versions.py）
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


if __name__ == "__main__":
    unittest.main()
