from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest


DEFAULT_SAMPLE_ROOT = Path(r"E:\Develop\lib\Samples")


@dataclass(frozen=True)
class SampleAsset:
    label: str
    category: str
    relative_path: str
    known_current_defect: str | None = None
    corrupted_fstring: bool = False


LEGACY_VERSION_DEFECT = (
    "current parser only supports UE5 legacy_file_version in {-9, -8}; "
    "this sample is UE4 legacy_file_version=-3"
)


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


DIAGNOSTIC_ASSETS = [
    SampleAsset(
        "third_person_character_blueprint",
        "Blueprint",
        r"ThirdPerson\Content\ThirdPerson\Blueprints\BP_ThirdPersonCharacter.uasset",
    ),
    SampleAsset(
        "manny_combat_anim_blueprint",
        "AnimBlueprint",
        r"ThirdPerson\Content\Variant_Combat\Anims\ABP_Manny_Combat.uasset",
    ),
    SampleAsset(
        "combat_character_blueprint",
        "Blueprint",
        r"ThirdPerson\Content\Variant_Combat\Blueprints\BP_CombatCharacter.uasset",
    ),
]


PARSER_ASSETS = [
    SampleAsset(
        "mannequin_material",
        "Material",
        r"FirstPerson\Content\Characters\Mannequins\Materials\M_Mannequin.uasset",
    ),
    SampleAsset(
        "manny_material_instance",
        "MaterialInstance",
        r"FirstPerson\Content\Characters\Mannequins\Materials\Manny\MI_Manny_01_New.uasset",
    ),
    SampleAsset(
        "grenade_launcher_skeletal_mesh",
        "SkeletalMesh",
        r"FirstPerson\Content\Weapons\GrenadeLauncher\Meshes\SKM_GrenadeLauncher.uasset",
    ),
    SampleAsset(
        "manny_texture",
        "Texture2D",
        r"ThirdPersonC\Content\Characters\Mannequins\Textures\Manny\T_Manny_01_BN.uasset",
    ),
]


SAMPLE_ASSETS_BY_LABEL = {
    asset.label: asset
    for asset in [*STABLE_ASSETS, *DIAGNOSTIC_ASSETS, *PARSER_ASSETS]
}


def configured_sample_root() -> Path:
    return Path(os.environ.get("UE_SAMPLE_ROOT", str(DEFAULT_SAMPLE_ROOT)))


def resolve_asset_path(sample_root: Path, relative_path: str | Path) -> Path:
    """Resolve canonical sample paths, including the historical ThirtPerson root."""
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
    path = resolve_asset_path(sample_root, relative_path)
    if not path.exists():
        pytest.skip(f"sample asset not found: {path}")
    return path


def pytest_param_for_asset(asset: SampleAsset):
    marks = []
    if asset.known_current_defect:
        marks.append(pytest.mark.xfail(reason=asset.known_current_defect, strict=True))
    return pytest.param(asset, id=f"{asset.category}:{asset.label}", marks=marks)


# ── 本地样本（tests/samples/ 目录）─────────────────────────────────────────────

LOCAL_SAMPLE_ROOT = Path(__file__).parent.parent / "samples"

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


def resolve_local_sample_path(sample: SampleAsset) -> Path:
    """解析本地样本文件路径。"""
    return LOCAL_SAMPLE_ROOT / sample.relative_path


def require_local_sample_path(sample: SampleAsset) -> Path:
    """获取本地样本路径，不存在时跳过测试。"""
    path = resolve_local_sample_path(sample)
    if not path.exists():
        pytest.skip(f"local sample not found: {path}")
    return path
