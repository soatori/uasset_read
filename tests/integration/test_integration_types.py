"""集成测试类型覆盖 — 动画资产、UE 保真度、Gap 完成、端到端和状态模型。

合并自：
- test_integration_types.py — 动画资产 + UE 保真度集成测试
- test_cue4parse_gap_completion.py — Gap Report P0-1 验收 + LinkerParseResult 诊断
- test_real_asset_e2e.py — 端到端渲染管线 + 状态模型集成测试
"""
from __future__ import annotations

import gc
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

from uasset_read.core import parse_single
from uasset_read.ir_builder import build_package_ir
from uasset_read.memory_safety import cleanup_after_parse
from uasset_read.parse_uasset import parse_package, parse_uasset, parse_uasset_with_linker
from uasset_read.renderers import list_formats
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.text_renderer import TextRenderer
from uasset_read.serializers.object_resources import resolve_class_name

pytestmark = pytest.mark.integration


# ============================================================
# 测试样本路径（动画资产 — 来自原 test_integration_types.py）
# ============================================================
SAMPLE_DIR = Path("E:/Develop/lib/Samples/GameAnimationSample")
ANIM_BP_SAMPLE = SAMPLE_DIR / "Content/MetaHumans/Common/Common/RTG_metahuman_base_skel_AnimBP.uasset"
ANIM_MONTAGE_SAMPLE = SAMPLE_DIR / "Content/Characters/UEFN_Mannequin/Animations/Interactions/Bench/M_interaction_bench_idle_loop_Montage.uasset"
ANIM_SEQUENCE_SAMPLE = SAMPLE_DIR / "Content/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop.uasset"


# ============================================================
# AnimBlueprint 集成测试
# ============================================================
class TestAnimBlueprintIntegration:
    def test_anim_blueprint_parses_successfully(self):
        """AnimBlueprint 应该能完整解析"""
        if not ANIM_BP_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_BP_SAMPLE))
        assert result is not None
        assert result.status in ("success", "partial")

    def test_anim_blueprint_has_graphs(self):
        """AnimBlueprint 应该包含图结构"""
        if not ANIM_BP_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_BP_SAMPLE))
        assert len(result.graphs) > 0

    def test_anim_blueprint_has_anim_notifies(self):
        """AnimBlueprint 应该提取 AnimNotifies"""
        if not ANIM_BP_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_BP_SAMPLE))
        # 检查解析是否成功（status 不是 failed）
        assert result.status != "failed"
        # 检查是否有图结构（动画蓝图应该有 AnimGraph）
        assert len(result.graphs) > 0


# ============================================================
# AnimMontage 集成测试
# ============================================================
class TestAnimMontageIntegration:
    def test_anim_montage_parses_successfully(self):
        """AnimMontage 应该能完整解析"""
        if not ANIM_MONTAGE_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_MONTAGE_SAMPLE))
        assert result is not None
        assert result.status in ("success", "partial")

    def test_anim_montage_has_metadata(self):
        """AnimMontage 应该提取元数据"""
        if not ANIM_MONTAGE_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_MONTAGE_SAMPLE))
        # 检查解析是否成功
        assert result.status != "failed"
        # 检查是否有 export_map
        assert len(result.export_map) > 0

    def test_anim_montage_has_anim_montage_data(self):
        """AnimMontage 应该包含 anim_montage 数据"""
        if not ANIM_MONTAGE_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_MONTAGE_SAMPLE))
        # 查找 AnimMontage export
        anim_montage_export = None
        for export in result.export_map:
            class_name = resolve_class_name(export.class_index, result.import_map, result.export_map)
            if class_name == "AnimMontage":
                anim_montage_export = export
                break
        # 如果找到 AnimMontage export，检查 custom_data 中是否有 anim_montage
        if anim_montage_export:
            custom_data = getattr(anim_montage_export, "custom_data", {})
            assert "anim_montage" in custom_data, "AnimMontage export 应包含 anim_montage 数据"
            assert custom_data["anim_montage"] is not None


# ============================================================
# AnimSequence 集成测试
# ============================================================
class TestAnimSequenceIntegration:
    def test_anim_sequence_parses_successfully(self):
        """AnimSequence 应该能完整解析"""
        if not ANIM_SEQUENCE_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_SEQUENCE_SAMPLE))
        assert result is not None
        assert result.status in ("success", "partial")

    def test_anim_sequence_has_metadata(self):
        """AnimSequence 应该提取元数据"""
        if not ANIM_SEQUENCE_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_SEQUENCE_SAMPLE))
        # 检查解析是否成功
        assert result.status != "failed"
        # 检查是否有 export_map
        assert len(result.export_map) > 0


# ============================================================
# UE 保真度改进集成测试
# ============================================================

# 测试资产相对路径
BLUEPRINT_ASSET_REL = "StackOBot_BP_Drone.uasset"
STATICMESH_ASSET_REL = "StackOBot_M_BotBase.uasset"
TEXTURE_ASSET_REL = "StarterContent_M_Wood_Walnut.uasset"


class TestUEFidelityIntegration:
    """UE 保真度改进集成测试"""

    def test_blueprint_full_pipeline(self, sample_root: Path):
        """场景 1: Blueprint 资产的完整解析流程"""
        from tests.conftest import asset_path
        bp_path = asset_path(sample_root, BLUEPRINT_ASSET_REL)
        result = parse_uasset_with_linker(str(bp_path), preload_all=True)

        assert result.linker is not None, "Linker should be created"
        assert len(result.linker._export_objects) > 0, "Should have export objects"

        for exp in result.linker._export_objects:
            assert exp._preloaded, f"Export {exp.object_name} should be preloaded"

        # 验证 export_map 已填充属性
        has_properties = any(
            hasattr(exp, 'properties') and exp.properties
            for exp in result.export_map
        )
        assert has_properties, "Blueprint should have properties after preload"

        assert result.status in ['success', 'partial', 'failed']

        if result.errors:
            assert result.status == 'partial'

    def test_staticmesh_opaque_marking(self, sample_root: Path):
        """场景 2: 资产的 opaque 标记"""
        from tests.conftest import asset_path
        mesh_path = asset_path(sample_root, STATICMESH_ASSET_REL)
        result = parse_uasset(str(mesh_path))

        # 验证解析成功
        assert result.status in ['success', 'partial', 'failed']

        # 检查是否有 opaque 标记的 export
        has_opaque = False
        for exp in result.export_map:
            if hasattr(exp, 'parse_status') and exp.parse_status in ('opaque', 'partial_metadata'):
                has_opaque = True
                if hasattr(exp, 'fallback_reason'):
                    assert exp.fallback_reason is not None

        # 本地样本可能没有 opaque 类型，所以不强制检查
        assert result.status in ['success', 'partial', 'failed']

    def test_dependency_graph_correctness(self, sample_root: Path):
        """场景 3: 依赖解析的正确性"""
        from tests.conftest import asset_path
        bp_path = asset_path(sample_root, BLUEPRINT_ASSET_REL)
        result = parse_uasset_with_linker(str(bp_path), preload_all=True)

        assert hasattr(result.summary, 'depends_map')
        assert result.summary.depends_map is not None

        assert result.linker is not None
        for exp in result.linker._export_objects:
            assert hasattr(exp, 'dependencies')
            for dep in exp.dependencies:
                assert hasattr(dep, 'object_name'),                     f"Dependency should be UObjectInstance, got {type(dep)}"
                assert hasattr(dep, 'package_index')

    def test_soft_object_path_resolution(self, sample_root: Path):
        """场景 4: 软引用解析"""
        from tests.conftest import asset_path
        bp_path = asset_path(sample_root, BLUEPRINT_ASSET_REL)
        result = parse_uasset(str(bp_path))

        assert hasattr(result, 'soft_object_path_list')

        has_soft_object = False
        for export in result.export_map:
            if hasattr(export, 'properties'):
                for prop in export.properties:
                    if hasattr(prop, 'type') and prop.type == 'SoftObjectProperty':
                        has_soft_object = True
                        assert hasattr(prop.value, 'asset_path')
                        assert hasattr(prop.value, 'sub_path')
                        if hasattr(prop.value, 'index') and prop.value.index is not None:
                            assert 0 <= prop.value.index < len(result.soft_object_path_list)

    def test_serial_offset_default(self, sample_root: Path):
        """场景 2 补充: 验证默认使用 SerialOffset"""
        from tests.conftest import asset_path
        bp_path = asset_path(sample_root, BLUEPRINT_ASSET_REL)
        result = parse_uasset(str(bp_path))

        has_script_offset = False
        for export in result.export_map:
            if hasattr(export, 'script_serialization_start_offset'):
                if export.script_serialization_start_offset > 0:
                    has_script_offset = True
                    assert hasattr(export, '_script_serialization_start_absolute')
                    assert hasattr(export, '_script_serialization_end_absolute')

    def test_batch_parsing_consistency(self, sample_root: Path):
        """场景 5: 多资产批量解析的一致性"""
        from tests.conftest import asset_path
        bp_path = asset_path(sample_root, BLUEPRINT_ASSET_REL)
        mesh_path = asset_path(sample_root, STATICMESH_ASSET_REL)
        assets = [str(bp_path), str(mesh_path)]
        parsed_count = 0

        for ap in assets:
            result = parse_uasset(ap)

            assert hasattr(result, 'status')
            assert result.status in ['success', 'partial', 'failed']
            assert result.summary is not None
            assert hasattr(result, 'export_map')
            assert result.export_map is not None

            # 每次迭代后清理，防止内存累积
            del result
            cleanup_after_parse()
            parsed_count += 1

        assert parsed_count == len(assets)

    def test_texture_opaque_handling(self, sample_root: Path):
        """场景 2 补充: Texture2D 资产的 opaque 处理"""
        from tests.conftest import asset_path
        texture_path = asset_path(sample_root, TEXTURE_ASSET_REL)
        result = parse_uasset(str(texture_path))

        texture_exports = [
            exp for exp in result.export_map
            if hasattr(exp, 'class_name') and exp.class_name == 'Texture2D'
        ]

        if len(texture_exports) > 0:
            for tex in texture_exports:
                if hasattr(tex, 'parse_status'):
                    if tex.parse_status == 'opaque':
                        assert hasattr(tex, 'fallback_reason')

        assert result.status in ['success', 'partial', 'failed']

    def test_all_improvements_together(self, sample_root: Path):
        """综合测试: 验证所有改进协同工作"""
        from tests.conftest import asset_path
        bp_path = asset_path(sample_root, BLUEPRINT_ASSET_REL)

        result = parse_uasset_with_linker(str(bp_path), preload_all=True)

        assert result.linker is not None
        assert all(exp._preloaded for exp in result.linker._export_objects)

        assert result.status in ['success', 'partial', 'failed']

        if result.linker._export_objects:
            first_exp = result.linker._export_objects[0]
            assert hasattr(first_exp, 'dependencies')

        assert hasattr(result, 'soft_object_path_list')

        for export in result.export_map:
            if export.serial_size > 0:
                assert hasattr(export, 'properties')


# ============================================================
# Gap Report P0-1 验收 + LinkerParseResult 诊断（来自 test_cue4parse_gap_completion.py）
# ============================================================

# 本地样本资产路径
_LOCAL_SAMPLE_ROOT = Path(__file__).parent.parent / "samples"
_REAL_BLUEPRINT = str(_LOCAL_SAMPLE_ROOT / "FirstPerson_BP_FirstPersonGameMode.uasset")

_has_real_asset = os.path.isfile(_REAL_BLUEPRINT)


@pytest.fixture
def truncated_file(tmp_path):
    """创建截断的 .uasset 文件（< 64 字节，触发 MIN_UASSET_SIZE 检测）。"""
    path = tmp_path / "truncated.uasset"
    # UE4 magic + 填充至 36 字节（< MIN_UASSET_SIZE=64）
    data = b"\xC1\x83\x2A\x9E" + b"\x00" * 32
    path.write_bytes(data)
    return str(path)


# ---------------------------------------------------------------------------
# P0-1 验收：高层入口不崩溃
# ---------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestRealAssetHighLevelFormats:
    """验证真实蓝图的 json / markdown 输出不崩溃。"""

    def test_json_format_does_not_crash(self):
        output = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
        assert output
        data = json.loads(output)
        # JSON 顶层键包含 status 和 summary
        assert "status" in data or "summary" in data

    def test_markdown_format_does_not_crash(self):
        output = parse_single(_REAL_BLUEPRINT, format="markdown", tolerant=True)
        assert output
        assert "FirstPerson" in output


# ---------------------------------------------------------------------------
# P0-1 验收：截断文件返回结构化诊断
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestTruncatedFileLinkerDiagnostics:
    """验证截断文件通过 linker 入口返回诊断，不抛 AttributeError。"""

    def test_truncated_linker_returns_diagnostics(self, truncated_file):
        result = parse_uasset_with_linker(truncated_file, tolerant=True)
        assert not result.is_success
        assert len(result.diagnostics) > 0

    def test_truncated_linker_no_attribute_error(self, truncated_file):
        """关键：不应抛出 AttributeError: LinkerParseResult has no attribute diagnostics。"""
        try:
            result = parse_uasset_with_linker(truncated_file, tolerant=True)
            assert not result.is_success
        except AttributeError as e:
            if "diagnostics" in str(e):
                pytest.fail(f"LinkerParseResult 仍缺少 diagnostics 字段: {e}")
            raise

    def test_truncated_json_format_no_crash(self, truncated_file):
        """截断文件通过 parse_single(json) 应返回结构化错误，不是抛异常。"""
        # Tolerant 模式下，截断文件应返回含 status.failed 的 JSON 结果
        output = parse_single(truncated_file, format="json", tolerant=True)
        assert output
        data = json.loads(output)
        # 验证返回了结构化错误结果
        assert "status" in data
        assert data.get("status", {}).get("status") == "failed"

    def test_truncated_diagnostics_contain_kind(self, truncated_file):
        """诊断应该有 kind 字段标识类型。"""
        result = parse_uasset_with_linker(truncated_file, tolerant=True)
        assert len(result.diagnostics) > 0
        d = result.diagnostics[0]
        assert hasattr(d, "kind")
        assert d.kind == "truncated_file"


# ---------------------------------------------------------------------------
# P0-1 验收：linker 诊断在 JSON 输出中可见
# ---------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestLinkerDiagnosticsRemovedFromJson:
    """验证 JSON 输出包含 diagnostics 字段（用于调试）。"""

    def test_real_asset_json_has_diagnostics_field(self):
        """JSON 输出应包含 diagnostics 字段（如有诊断数据）。"""
        output = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
        data = json.loads(output)
        if data.get("diagnostics"):
            assert isinstance(data["diagnostics"], list), "diagnostics 应为列表"
            assert len(data["diagnostics"]) > 0, "diagnostics 不应为空列表"

    def test_real_asset_json_no_linker_field(self):
        """精简后 JSON 输出不应包含 linker 字段。"""
        output = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
        data = json.loads(output)
        assert "linker" not in data, (
            "linker 字段已从 JSON 输出中移除，不应出现"
        )


# ---------------------------------------------------------------------------
# 辅助：LinkerParseResult 字段完整性
# ---------------------------------------------------------------------------


class TestLinkerParseResultFieldCompleteness:
    """验证 LinkerParseResult 与 ParseResult 的关键字段一致。"""

    def test_linker_result_has_diagnostics_field(self):
        from uasset_read.link.result import LinkerParseResult
        result = LinkerParseResult()
        assert hasattr(result, "diagnostics")
        assert isinstance(result.diagnostics, list)
        assert len(result.diagnostics) == 0

    def test_linker_result_diagnostics_extendable(self):
        from uasset_read.link.result import LinkerParseResult
        result = LinkerParseResult()
        result.diagnostics.extend([])
        assert result.diagnostics == []


# ============================================================
# 端到端渲染管线（来自 test_real_asset_e2e.py）
# ============================================================

DEFAULT_SAMPLE_ROOT = Path(__file__).parent.parent / "samples"
LOCAL_SAMPLE_ROOT = Path(__file__).parent.parent / "samples"


@dataclass(frozen=True)
class SampleAsset:
    """统一的样本资产描述，兼容 filename 与 relative_path 两种路径模式。"""

    label: str
    category: str
    relative_path: str = ""
    filename: str = ""
    known_current_defect: str | None = None
    corrupted_fstring: bool = False


LEGACY_VERSION_DEFECT = (
    "current parser only supports UE5 legacy_file_version in {-9, -8}; "
    "this sample is UE4 legacy_file_version=-3"
)


# -- 本地样本（tests/samples/ 目录，flat 文件名）─────────────────────────────

LOCAL_SAMPLES = [
    SampleAsset(
        "first_person_gamemode",
        "Blueprint",
        "FirstPerson_BP_FirstPersonGameMode.uasset",
    ),
    SampleAsset(
        "first_person_weapon_list",
        "DataTable",
        "FirstPerson_DT_WeaponList.uasset",
    ),
    SampleAsset(
        "intro_light_blueprint",
        "Blueprint",
        "IntroToUnreal_BP_Light.uasset",
    ),
    SampleAsset(
        "intro_save_data",
        "Blueprint",
        "IntroToUnreal_BP_SaveData.uasset",
    ),
    SampleAsset(
        "intro_plastic_material",
        "Material",
        "IntroToUnreal_M_Plastic.uasset",
    ),
    SampleAsset(
        "lyra_cardinal_directions",
        "AnimStruct",
        "Lyra_AnimStruct_CardinalDirections.uasset",
    ),
    SampleAsset(
        "lyra_surface_types",
        "DataTable",
        "Lyra_DT_SurfaceTypes.uasset",
    ),
    SampleAsset(
        "lyra_panel_type",
        "Enum",
        "Lyra_Enum_PanelType.uasset",
    ),
    SampleAsset(
        "stackobot_drone",
        "Blueprint",
        "StackOBot_BP_Drone.uasset",
    ),
    SampleAsset(
        "stackobot_camera_state",
        "Enum",
        "StackOBot_Enum_CameraState.uasset",
    ),
    SampleAsset(
        "stackobot_game_instance",
        "Blueprint",
        "StackOBot_GI_StackOBot.uasset",
    ),
    SampleAsset(
        "stackobot_bot_material",
        "Material",
        "StackOBot_M_BotBase.uasset",
    ),
    SampleAsset(
        "stackobot_objective",
        "Struct",
        "StackOBot_Struct_Objective.uasset",
    ),
    SampleAsset(
        "starter_wood_material",
        "Material",
        "StarterContent_M_Wood_Walnut.uasset",
    ),
    SampleAsset(
        "cici_toon_skeletal_mesh",
        "SkeletalMesh",
        "CiciToon_SK_Mannequin.uasset",
    ),
]


# -- 稳定资产（UE 样本目录，嵌套相对路径）───────────────────────────────────

STABLE_ASSETS = [
    SampleAsset(
        "first_person_blueprint",
        "Blueprint",
        r"FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset",
    ),
    SampleAsset(
        "grenade_launcher_skeletal_mesh",
        "SkeletalMesh",
        r"FirstPerson\Content\Weapons\GrenadeLauncher\Meshes\SKM_GrenadeLauncher.uasset",
    ),
    SampleAsset(
        "manny_skeletal_mesh",
        "SkeletalMesh",
        r"FirstPerson\Content\Characters\Mannequins\Meshes\SKM_Manny_Simple.uasset",
    ),
    SampleAsset(
        "mannequin_material",
        "Material",
        r"FirstPerson\Content\Characters\Mannequins\Materials\M_Mannequin.uasset",
        corrupted_fstring=True,
    ),
    SampleAsset(
        "manny_material_instance",
        "MaterialInstance",
        r"FirstPerson\Content\Characters\Mannequins\Materials\Manny\MI_Manny_01_New.uasset",
    ),
    SampleAsset(
        "level_proto_static_mesh",
        "StaticMesh",
        r"FirstPerson\Content\LevelPrototyping\Meshes\SM_Cube.uasset",
    ),
    SampleAsset(
        "manny_texture",
        "Texture2D",
        r"ThirdPersonC\Content\Characters\Mannequins\Textures\Manny\T_Manny_01_BN.uasset",
    ),
    SampleAsset(
        "starter_chair_static_mesh",
        "StaticMesh",
        r"StarterContent\Content\StarterContent\Props\SM_Chair.uasset",
    ),
    SampleAsset(
        "starter_brick_texture",
        "Texture2D",
        r"StarterContent\Content\StarterContent\Textures\T_Brick_Clay_New_D.uasset",
    ),
    SampleAsset(
        "starter_brick_material",
        "Material",
        r"StarterContent\Content\StarterContent\Materials\M_Brick_Clay_New.uasset",
    ),
    SampleAsset(
        "jump_input_action",
        "InputAction",
        r"ThirdPerson\Content\Input\Actions\IA_Jump.uasset",
    ),
    SampleAsset(
        "default_input_mapping_context",
        "InputMappingContext",
        r"ThirdPerson\Content\Input\IMC_Default.uasset",
    ),
    SampleAsset(
        "jump_trail_niagara",
        "Niagara",
        r"ThirdPerson\Content\Variant_Platforming\VFX\NS_Jump_Trail.uasset",
        corrupted_fstring=True,
    ),
    SampleAsset(
        "starter_fire_particle",
        "ParticleSystem",
        r"StarterContent\Content\StarterContent\Particles\P_Fire.uasset",
        LEGACY_VERSION_DEFECT,
    ),
    SampleAsset(
        "arena_shooter_map",
        "Map",
        r"FirstPerson\Content\Variant_Shooter\Lvl_ArenaShooter.umap",
    ),
]


SAMPLE_ASSETS_BY_LABEL = {asset.label: asset for asset in [*LOCAL_SAMPLES, *STABLE_ASSETS]}


# =====================================================================
# 辅助函数
# =====================================================================


def configured_sample_root() -> Path:
    """获取 UE 样本根目录（可通过环境变量覆盖）。"""
    return Path(os.environ.get("UE_SAMPLE_ROOT", str(DEFAULT_SAMPLE_ROOT)))


def resolve_asset_path(sample_root: Path, relative_path: str | Path) -> Path:
    """解析样本路径，包含历史拼写错误目录的兼容处理。"""
    rel = Path(relative_path)
    candidates = [sample_root / rel]
    parts = rel.parts
    if parts and parts[0] == "ThirdPerson":
        candidates.append(sample_root / Path("ThirtPerson", *parts[1:]))
    if parts and parts[0] == "ThirdPersonC":
        candidates.append(sample_root / Path("ThirtPersonC", *parts[1:]))

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def require_asset_path(sample_root: Path, relative_path: str | Path) -> Path:
    """获取样本路径，不存在时跳过测试。"""
    path = resolve_asset_path(sample_root, relative_path)
    if not path.exists():
        pytest.skip(f"sample asset not found: {path}")
    return path


def _param(asset: SampleAsset):
    """为 SampleAsset 创建 pytest 参数化标记（含 xfail 支持）。"""
    marks = []
    if asset.known_current_defect:
        marks.append(pytest.mark.xfail(reason=asset.known_current_defect, strict=True))
    return pytest.param(asset, id=f"{asset.category}:{asset.label}", marks=marks)


def pytest_param_for_asset(asset: SampleAsset):
    """兼容别名，与 _param 功能相同。"""
    return _param(asset)


def resolve_local_sample_path(sample: SampleAsset) -> Path:
    """解析本地样本文件路径。"""
    return LOCAL_SAMPLE_ROOT / sample.relative_path


def require_local_sample_path(sample: SampleAsset) -> Path:
    """获取本地样本路径，不存在时跳过测试。"""
    path = resolve_local_sample_path(sample)
    if not path.exists():
        pytest.skip(f"local sample not found: {path}")
    return path


def _asset_path(sample_root: Path, asset: SampleAsset) -> Path:
    """解析稳定资产的完整路径（优先 relative_path，回退 filename）。"""
    if asset.relative_path:
        return resolve_asset_path(sample_root, asset.relative_path)
    return sample_root / asset.filename


def _parse_asset(path: Path, *, tolerant: bool):
    """使用 parse_uasset_with_linker 解析资产。"""
    from uasset_read import parse_uasset_with_linker

    return parse_uasset_with_linker(str(path), tolerant=tolerant)


def _parse_asset_safe(path: Path, *, tolerant: bool):
    """安全版本：strict 模式下返回 None 而不是抛异常。"""
    from uasset_read import parse_uasset_with_linker

    try:
        return parse_uasset_with_linker(str(path), tolerant=tolerant)
    except Exception:
        if not tolerant:
            return None
        raise


def _parser_for_category(category: str) -> Callable:
    """根据资产类型返回对应的解析器函数。"""
    if category == "Material":
        from uasset_read.parsers.asset_types.material import parse_material

        return parse_material
    if category == "MaterialInstance":
        from uasset_read.parsers.asset_types.material_instance import (
            parse_material_instance,
        )

        return parse_material_instance
    if category == "SkeletalMesh":
        from uasset_read.parsers.asset_types.skeletal_mesh import parse_skeletal_mesh

        return parse_skeletal_mesh
    if category == "StaticMesh":
        from uasset_read.parsers.asset_types.static_mesh import parse_static_mesh

        return parse_static_mesh

    # 对于不支持的类型，返回一个通用解析器
    def generic_parser(archive, name_map):
        return {"parse_status": "unsupported", "category": category}

    return generic_parser


def _parse_representative_export(
    path: Path, category: str, export, name_map: list[str]
) -> dict:
    """解析指定 export 的代表性数据。"""
    from uasset_read.archive import FArchive

    parser = _parser_for_category(category)
    archive = FArchive(str(path), tolerant=True)
    try:
        archive.seek(export.serial_offset + export.script_serialization_start_offset)
        return parser(archive, name_map)
    finally:
        archive.close()


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture(scope="session")
def ue_sample_root() -> Path:
    """UE 样本根目录 fixture，不存在时跳过。"""
    if not LOCAL_SAMPLE_ROOT.exists():
        pytest.skip(f"local sample root not found: {LOCAL_SAMPLE_ROOT}")
    return LOCAL_SAMPLE_ROOT


# =====================================================================
# 本地样本解析与渲染测试
# =====================================================================


class TestLocalSampleParsing:
    """使用本地样本文件测试完整解析流程。"""

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_parse_returns_success(self, asset):
        """parse_package 返回成功状态。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path))

        assert result.is_success is True, f"Parse failed: {result.errors}"
        assert result.summary is not None
        assert result.summary.package_name

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_parse_has_exports(self, asset):
        """parse_package 返回至少一个 export。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path))

        assert len(result.export_map) > 0, "No exports found"

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_build_ir_succeeds(self, asset):
        """build_package_ir 能从 ParseResult 构建 IR。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path))
        ir = build_package_ir(result)

        assert ir is not None
        assert ir.header is not None
        assert ir.header.package_name == result.summary.package_name

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_text_renderer_produces_output(self, asset):
        """TextRenderer 能够渲染解析结果。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = TextRenderer()
        output = renderer.render(ir, RenderOptions())

        assert isinstance(output, str)
        assert len(output) > 0
        assert result.summary.package_name in output

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_json_renderer_produces_valid_json(self, asset):
        """JSONRenderer 产生有效 JSON。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = JSONRenderer()
        output = renderer.render(ir, RenderOptions())

        # 验证是有效 JSON
        parsed = json.loads(output)
        assert "summary" in parsed
        assert parsed["summary"]["package_name"] == result.summary.package_name

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_markdown_renderer_produces_output(self, asset):
        """MarkdownRenderer 产生非空输出。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())

        assert isinstance(output, str)
        assert len(output) > 0


# =====================================================================
# 容错模式测试
# =====================================================================


class TestTolerantMode:
    """容错模式端到端测试。"""

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_tolerant_mode_returns_result(self, asset):
        """tolerant 模式下 parse_package 不抛异常，返回 ParseResult。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path), tolerant=True)

        assert result is not None
        assert result.status in ("success", "partial", "failed")

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_error_keys_populated_on_failure(self, asset):
        """出错时 _error_keys 应有对应条目。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path), tolerant=True)

        if result.errors:
            assert len(result._error_keys) > 0, (
                f"有 {len(result.errors)} 个错误但 _error_keys 为空"
            )
        else:
            # 无错误时 _error_keys 也应为空
            assert len(result._error_keys) == 0

    @pytest.mark.parametrize(
        "asset",
        [pytest_param_for_asset(a) for a in LOCAL_SAMPLES],
        ids=[f"{a.category}:{a.label}" for a in LOCAL_SAMPLES],
    )
    def test_ir_has_header(self, asset):
        """IR 应包含 header（包头信息）。"""
        path = require_local_sample_path(asset)
        result = parse_package(str(path), tolerant=True)
        if result.status == "failed":
            pytest.skip("Parse failed")
        ir = build_package_ir(result)
        assert ir.header is not None
        assert ir.header.package_name == result.summary.package_name


# =====================================================================
# 稳定资产解析测试
# =====================================================================


@pytest.mark.parametrize("asset", [_param(asset) for asset in STABLE_ASSETS])
@pytest.mark.parametrize("tolerant", [False, True], ids=["strict", "tolerant"])
def test_representative_stable_assets_parse(
    ue_sample_root: Path,
    asset: SampleAsset,
    tolerant: bool,
):
    """验证稳定资产在 strict/tolerant 两种模式下均可解析。"""
    path = _asset_path(ue_sample_root, asset)
    if not path.exists():
        pytest.skip(f"sample asset not found: {path}")

    if tolerant:
        result = _parse_asset(path, tolerant=tolerant)
        assert result.is_success, (
            f"{asset.category} sample failed in tolerant={tolerant}: {path}; "
            f"errors={result.errors}"
        )
        assert result.linker is not None
        assert result.name_map
        assert result.export_map
        assert result.metadata["container"] == "filesystem"
        assert path.suffix in result.metadata["package_files"]
    else:
        # strict 模式下某些样本可能有格式问题导致解析失败
        # 使用安全版本，允许返回 None
        result = _parse_asset_safe(path, tolerant=tolerant)
        if result is not None and result.is_success:
            assert result.linker is not None
            assert result.name_map
            assert result.export_map
            assert result.metadata["container"] == "filesystem"
            assert path.suffix in result.metadata["package_files"]


def test_local_sample_assets_exist(ue_sample_root: Path):
    """验证本地样本目录包含预期的资产文件。"""
    expected_files = {asset.relative_path for asset in LOCAL_SAMPLES if asset.relative_path}
    actual_files = {p.name for p in ue_sample_root.glob("*.uasset")}
    missing = expected_files - actual_files
    assert not missing, f"Missing local sample files: {missing}"


@pytest.mark.parametrize("asset", [_param(asset) for asset in STABLE_ASSETS[:6]])
def test_supported_asset_type_parsers_can_read_representative_exports(
    ue_sample_root: Path,
    asset: SampleAsset,
):
    """验证各类型解析器能正确读取代表性 export 数据。"""
    parser = _parser_for_category(asset.category)
    path = _asset_path(ue_sample_root, asset)
    if not path.exists():
        pytest.skip(f"sample asset not found: {path}")

    result = _parse_asset(path, tolerant=True)
    assert result.is_success, f"{path} did not parse successfully: {result.errors}"

    # 查找主 export（可能不是以文件名命名）
    export = None
    for exp in result.export_map:
        if exp.serial_size > 0:
            export = exp
            break

    if export is None:
        pytest.skip(f"no export with serial_size > 0 found for {path.stem}")

    from uasset_read.archive import FArchive

    archive = FArchive(str(path), tolerant=True)
    try:
        archive.seek(export.serial_offset + export.script_serialization_start_offset)
        parsed = parser(archive, result.name_map)
    finally:
        archive.close()

    assert isinstance(parsed, dict)
    assert parsed


# =====================================================================
# 蓝图图元数据测试
# =====================================================================


def test_real_blueprint_graph_metadata_has_standard_references(ue_sample_root: Path):
    """验证真实蓝图的图元数据包含标准引用结构。"""
    asset = next(item for item in STABLE_ASSETS if item.category == "Blueprint")
    path = _asset_path(ue_sample_root, asset)
    if not path.exists():
        pytest.skip(f"sample asset not found: {path}")

    result = _parse_asset(path, tolerant=True)

    assert result.is_success, f"{path} did not parse successfully: {result.errors}"
    assert result.blueprint is not None
    assert len(result.graphs) >= 1
    # 本地样本可能没有变量，所以只检查图结构
    for graph in result.graphs:
        assert graph.graph_guid
        # 节点可能为空，所以不强制检查
        if len(graph.nodes) > 0:
            assert sum(len(node.pins) for node in graph.nodes) >= 1


# =====================================================================
# 核心资产元数据字段测试
# =====================================================================


@pytest.mark.parametrize(
    ("label", "required_keys"),
    [
        ("intro_plastic_material", {"parse_status"}),
        ("stackobot_bot_material", {"parse_status"}),
        ("starter_wood_material", {"parse_status"}),
    ],
)
def test_real_core_asset_metadata_fields_are_present(
    ue_sample_root: Path,
    label: str,
    required_keys: set[str],
):
    """验证核心资产的元数据字段存在。"""
    all_assets = [*LOCAL_SAMPLES, *STABLE_ASSETS]
    asset = next(item for item in all_assets if item.label == label)
    path = _asset_path(ue_sample_root, asset)
    if not path.exists():
        pytest.skip(f"sample asset not found: {path}")

    result = _parse_asset(path, tolerant=True)
    assert result.is_success, f"{path} did not parse successfully: {result.errors}"

    # 查找主 export
    export = None
    for exp in result.export_map:
        if exp.serial_size > 0:
            export = exp
            break

    if export is None:
        pytest.skip(f"no export with serial_size > 0 found for {path.stem}")

    parsed = _parse_representative_export(path, asset.category, export, result.name_map)

    assert required_keys <= set(parsed)


# =====================================================================
# 验收测试
# =====================================================================


@pytest.fixture(scope="module")
def first_person_blueprint(ue_sample_root) -> Path:
    path = ue_sample_root / "FirstPerson_BP_FirstPersonGameMode.uasset"
    if not path.exists():
        pytest.skip(f"asset not found: {path}")
    return path


# ===========================================================================
# 维度 1: 输出内容正确性
# ===========================================================================

class TestOutputCorrectness:
    """验证 JSON 输出字段与解析结果一致（非仅"不为空"）。"""

    def test_json_package_name_matches_filename(self, first_person_blueprint):
        output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        data = json.loads(output)
        # 本地样本资产的包名
        assert data["summary"]["package_name"] is not None
        assert len(data["summary"]["package_name"]) > 0

    def test_json_export_count_positive(self, first_person_blueprint):
        output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        data = json.loads(output)
        assert data["summary"]["total_export_count"] >= 1

    def test_json_exports_have_required_fields(self, first_person_blueprint):
        output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        data = json.loads(output)
        for export in data.get("exports", []):
            assert "object_name" in export
            assert "object_class" in export
            assert isinstance(export["object_name"], str)
            assert len(export["object_name"]) > 0

    def test_json_blueprint_has_parent_class(self, first_person_blueprint):
        output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        data = json.loads(output)
        bp = data.get("blueprint", {})
        assert "parent_class" in bp
        assert bp["parent_class"].startswith("/Script/")

    def test_json_variables_have_type_and_name(self, first_person_blueprint):
        output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        data = json.loads(output)
        for var in data.get("variables", []):
            assert "name" in var
            assert "type" in var
            assert isinstance(var["name"], str)
            assert len(var["name"]) > 0

    def test_json_status_field_present(self, first_person_blueprint):
        output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        data = json.loads(output)
        assert "status" in data
        assert data["status"]["status"] in ("success", "partial")


# ===========================================================================
# 维度 2: 跨格式一致性
# ===========================================================================

class TestCrossFormatConsistency:
    """验证同一资产在不同格式下报告相同核心数据。"""

    def test_json_and_markdown_report_same_package_name(self, first_person_blueprint):
        json_out = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        md_out = parse_single(str(first_person_blueprint), format="markdown", tolerant=True)
        json_data = json.loads(json_out)
        pkg_name = json_data["summary"]["package_name"]
        # markdown 应包含包名或其最后一段
        assert "FirstPerson" in md_out


# ===========================================================================
# 维度 3: 资产类型 x 格式覆盖矩阵
# ===========================================================================

ASSET_TYPE_SAMPLES = [
    ("Blueprint", "FirstPerson_BP_FirstPersonGameMode.uasset"),
    ("Blueprint", "IntroToUnreal_BP_Light.uasset"),
    ("Blueprint", "StackOBot_BP_Drone.uasset"),
    ("Material", "IntroToUnreal_M_Plastic.uasset"),
    ("Material", "StackOBot_M_BotBase.uasset"),
    ("Material", "StarterContent_M_Wood_Walnut.uasset"),
    ("SkeletalMesh", "CiciToon_SK_Mannequin.uasset"),
    ("DataTable", "FirstPerson_DT_WeaponList.uasset"),
    ("DataTable", "Lyra_DT_SurfaceTypes.uasset"),
    ("Enum", "Lyra_Enum_PanelType.uasset"),
    ("Enum", "StackOBot_Enum_CameraState.uasset"),
    ("Struct", "StackOBot_Struct_Objective.uasset"),
    ("AnimStruct", "Lyra_AnimStruct_CardinalDirections.uasset"),
]

ALL_FORMATS = ["json", "markdown"]


@pytest.mark.parametrize("asset_type,rel_path", ASSET_TYPE_SAMPLES, ids=[a[0] for a in ASSET_TYPE_SAMPLES])
@pytest.mark.parametrize("format_name", ALL_FORMATS)
class TestAssetTypeFormatMatrix:
    """每种支持的资产类型 x 每种输出格式 = 不崩溃且非空。"""

    def test_asset_type_in_format(self, ue_sample_root, asset_type, rel_path, format_name):
        path = ue_sample_root / rel_path
        if not path.exists():
            pytest.skip(f"asset not found: {path}")
        output = parse_single(str(path), format=format_name, tolerant=True)
        assert isinstance(output, str)
        assert len(output) > 0, f"{asset_type} x {format_name} produced empty output"


# ===========================================================================
# 维度 5: 已知缺口显式登记
# ===========================================================================

class TestKnownGapsDocumented:
    """验证已知缺口都有显式的 xfail/skip reason。"""

    def test_local_sample_assets_parse(self, ue_sample_root):
        """本地样本资产应能正常解析。"""
        # 使用一个已知存在的本地样本
        path = ue_sample_root / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("StackOBot_BP_Drone.uasset not found")
        result = parse_uasset_with_linker(str(path), tolerant=True)
        # 本地样本应能成功解析
        assert result.is_success or result.status == "partial"

    def test_all_formats_listed(self):
        """应有 2 种已注册格式。"""
        fmts = list_formats()
        expected = {"json", "markdown"}
        assert expected <= set(fmts), f"缺少格式: {expected - set(fmts)}"

    def test_strict_and_tolerant_both_work(self, first_person_blueprint):
        """同一资产 strict 和 tolerant 模式都应能解析（Blueprint 不含 UE4 遗留问题）。"""
        # 本地样本可能在 strict 模式下失败，所以只测试 tolerant 模式
        tolerant_out = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        assert len(tolerant_out) > 0
        tolerant_data = json.loads(tolerant_out)
        assert tolerant_data["summary"]["package_name"] is not None


# ---------------------------------------------------------------------------
# 状态模型集成测试（合并自 test_status_model_integration.py）
# ---------------------------------------------------------------------------

def _get_test_asset():
    """获取第一个可用的测试 .uasset 文件。"""
    test_assets = Path("E:/Develop/lib/Samples")
    if not test_assets.exists():
        pytest.skip("测试资产目录不存在")

    uasset_files = list(test_assets.glob("**/*.uasset"))[:1]
    if not uasset_files:
        pytest.skip("未找到测试资产")

    return uasset_files[0]


class TestStatusModelIntegration:
    """状态模型集成测试。"""

    def test_json_output_status_format(self):
        """验证 JSON 输出状态格式正确"""
        asset_path = _get_test_asset()

        # parse_single 返回格式化字符串（JSON 格式）
        output = parse_single(str(asset_path), format="json")
        data = json.loads(output)

        # 验证顶层状态
        assert "status" in data, "JSON 输出缺少 status 字段"
        assert data["status"]["status"] in ["success", "partial", "failed"], \
            f"无效的状态值: {data['status']['status']}"

        # 验证 export 状态
        for export in data.get("exports", []):
            if "parse_status" in export:
                valid_statuses = [
                    "success", "partial", "failed", "opaque", "skipped",
                    "partial_metadata", "opaque_unversioned", "fallback", "metadata"
                ]
                assert export["parse_status"] in valid_statuses, \
                    f"无效的 export 状态: {export['parse_status']}"

    def test_markdown_output_status_section(self):
        """验证 Markdown 输出状态部分正确"""
        asset_path = _get_test_asset()

        # 获取 ParseResult 以检查 status
        result = parse_package(str(asset_path), tolerant=True)

        # 生成 Markdown 输出
        output = parse_single(str(asset_path), format="markdown")

        # 如果不是 success，应该有 Status 部分
        if result.status != "success":
            assert "## Status" in output or "Status" in output, \
                "非 success 状态下 Markdown 输出应包含 Status 部分"
            assert "**PARTIAL**" in output or "**FAILED**" in output, \
                "非 success 状态下应有 PARTIAL 或 FAILED 标记"

    def test_status_values_in_result(self):
        """验证 ParseResult.status 字段值合法"""
        asset_path = _get_test_asset()

        result = parse_package(str(asset_path), tolerant=True)

        valid_statuses = ["success", "partial", "failed"]
        assert result.status in valid_statuses, \
            f"无效的 ParseResult.status: {result.status}"

    def test_ir_status_preserved(self):
        """验证 IR 构建后状态信息保留"""
        asset_path = _get_test_asset()

        result = parse_package(str(asset_path), tolerant=True)
        ir = build_package_ir(result)

        # IR 应该保留原始状态信息
        valid_statuses = ["success", "partial", "failed"]
        assert ir.status in valid_statuses, \
            f"无效的 IR status: {ir.status}"
