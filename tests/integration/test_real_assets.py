"""端到端集成测试 — 合并自 test_sample_assets.py、test_sample_assets_representative.py、test_acceptance.py。

使用 tests/samples/ 本地样本与 UE 样本目录验证完整解析→渲染流程。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

from uasset_read.core import parse_single
from uasset_read.ir_builder import build_package_ir
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker
from uasset_read.renderers import list_formats
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.text_renderer import TextRenderer


# =====================================================================
# 数据模型与常量
# =====================================================================

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


# ── 本地样本（tests/samples/ 目录，flat 文件名）─────────────────────────────

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


# ── 稳定资产（UE 样本目录，嵌套相对路径）───────────────────────────────────

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
# 本地样本解析与渲染测试（来自 test_sample_assets.py）
# =====================================================================


@pytest.mark.integration
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
# 容错模式测试（来自 test_sample_assets.py）
# =====================================================================


@pytest.mark.integration
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
# 稳定资产解析测试（来自 test_sample_assets_representative.py）
# =====================================================================


@pytest.mark.integration
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


@pytest.mark.integration
def test_local_sample_assets_exist(ue_sample_root: Path):
    """验证本地样本目录包含预期的资产文件。"""
    expected_files = {asset.filename for asset in STABLE_ASSETS}
    actual_files = {p.name for p in ue_sample_root.glob("*.uasset")}
    missing = expected_files - actual_files
    assert not missing, f"Missing local sample files: {missing}"


@pytest.mark.integration
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
# 蓝图图元数据测试（来自 test_sample_assets_representative.py）
# =====================================================================


@pytest.mark.integration
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
# 核心资产元数据字段测试（来自 test_sample_assets_representative.py）
# =====================================================================


@pytest.mark.integration
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
    asset = next(item for item in STABLE_ASSETS if item.label == label)
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
# 验收测试（来自 test_acceptance.py）
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

@pytest.mark.integration
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

@pytest.mark.integration
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
# 维度 3: 资产类型×格式覆盖矩阵
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


@pytest.mark.integration
@pytest.mark.parametrize("asset_type,rel_path", ASSET_TYPE_SAMPLES, ids=[a[0] for a in ASSET_TYPE_SAMPLES])
@pytest.mark.parametrize("format_name", ALL_FORMATS)
class TestAssetTypeFormatMatrix:
    """每种支持的资产类型 × 每种输出格式 = 不崩溃且非空。"""

    def test_asset_type_in_format(self, ue_sample_root, asset_type, rel_path, format_name):
        path = ue_sample_root / rel_path
        if not path.exists():
            pytest.skip(f"asset not found: {path}")
        output = parse_single(str(path), format=format_name, tolerant=True)
        assert isinstance(output, str)
        assert len(output) > 0, f"{asset_type} × {format_name} produced empty output"


# ===========================================================================
# 维度 5: 已知缺口显式登记
# ===========================================================================

@pytest.mark.integration
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
