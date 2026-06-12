from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest


DEFAULT_SAMPLE_ROOT = Path(r"E:\Develop\lib\UnrealEngine\Samples")


@dataclass(frozen=True)
class SampleAsset:
    label: str
    category: str
    relative_path: str
    known_current_defect: str | None = None


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
        "level_proto_texture",
        "Texture2D",
        r"FirstPerson\Content\LevelPrototyping\Textures\T_GridChecker_A.uasset",
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
        r"ThirtPerson\Content\Input\Actions\IA_Jump.uasset",
    ),
    SampleAsset(
        "default_input_mapping_context",
        "InputMappingContext",
        r"ThirtPerson\Content\Input\IMC_Default.uasset",
    ),
    SampleAsset(
        "jump_trail_niagara",
        "Niagara",
        r"ThirtPerson\Content\Variant_Platforming\VFX\NS_Jump_Trail.uasset",
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
        r"ThirtPerson\Content\ThirdPerson\Blueprints\BP_ThirdPersonCharacter.uasset",
    ),
    SampleAsset(
        "manny_combat_anim_blueprint",
        "AnimBlueprint",
        r"ThirtPerson\Content\Variant_Combat\Anims\ABP_Manny_Combat.uasset",
    ),
    SampleAsset(
        "combat_character_blueprint",
        "Blueprint",
        r"ThirtPerson\Content\Variant_Combat\Blueprints\BP_CombatCharacter.uasset",
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
        "level_proto_texture",
        "Texture2D",
        r"FirstPerson\Content\LevelPrototyping\Textures\T_GridChecker_A.uasset",
    ),
]


def _asset_path(sample_root: Path, asset: SampleAsset) -> Path:
    return sample_root / Path(asset.relative_path)


def _param(asset: SampleAsset):
    marks = []
    if asset.known_current_defect:
        marks.append(pytest.mark.xfail(reason=asset.known_current_defect, strict=True))
    return pytest.param(asset, id=f"{asset.category}:{asset.label}", marks=marks)


@pytest.fixture(scope="session")
def ue_sample_root() -> Path:
    root = Path(os.environ.get("UE_SAMPLE_ROOT", str(DEFAULT_SAMPLE_ROOT)))
    if not root.exists():
        pytest.skip(f"sample root not found: {root}")
    return root


def _parse_asset(path: Path, *, tolerant: bool):
    from uasset_read import parse_uasset_with_linker

    return parse_uasset_with_linker(str(path), tolerant=tolerant)


@pytest.mark.integration
@pytest.mark.parametrize("asset", [_param(asset) for asset in STABLE_ASSETS])
@pytest.mark.parametrize("tolerant", [False, True], ids=["strict", "tolerant"])
def test_representative_stable_assets_parse(
    ue_sample_root: Path,
    asset: SampleAsset,
    tolerant: bool,
):
    path = _asset_path(ue_sample_root, asset)
    if not path.exists():
        pytest.skip(f"sample asset not found: {path}")

    result = _parse_asset(path, tolerant=tolerant)

    assert result.is_success, (
        f"{asset.category} sample failed in tolerant={tolerant}: {path}; "
        f"errors={result.errors}"
    )
    assert result.summary is not None
    assert result.linker is not None
    assert result.name_map
    assert result.export_map
    assert result.metadata["container"] == "filesystem"
    assert path.suffix in result.metadata["package_files"]


@pytest.mark.integration
@pytest.mark.parametrize("asset", [_param(asset) for asset in PARSER_ASSETS])
def test_supported_asset_type_parsers_can_read_representative_exports(
    ue_sample_root: Path,
    asset: SampleAsset,
):
    parser = _parser_for_category(asset.category)
    path = _asset_path(ue_sample_root, asset)
    if not path.exists():
        pytest.skip(f"sample asset not found: {path}")

    result = _parse_asset(path, tolerant=True)
    assert result.is_success, f"{path} did not parse successfully: {result.errors}"

    export = next(
        (
            export
            for export in result.export_map
            if export.object_name == path.stem and export.serial_size > 0
        ),
        None,
    )
    assert export is not None, f"no primary export found for {path.stem}"

    from uasset_read.archive import FArchive

    archive = FArchive(str(path), tolerant=True)
    try:
        archive.seek(export.serial_offset + export.script_serialization_start_offset)
        parsed = parser(archive, result.name_map)
    finally:
        archive.close()

    assert isinstance(parsed, dict)
    assert parsed


@pytest.mark.integration
def test_real_blueprint_graph_metadata_has_standard_references(ue_sample_root: Path):
    asset = STABLE_ASSETS[0]
    path = _asset_path(ue_sample_root, asset)
    if not path.exists():
        pytest.skip(f"sample asset not found: {path}")

    result = _parse_asset(path, tolerant=True)

    assert result.is_success, f"{path} did not parse successfully: {result.errors}"
    assert result.blueprint is not None
    assert len(result.blueprint.variables) >= 1
    assert any(variable.var_guid for variable in result.blueprint.variables)
    assert len(result.graphs) >= 1
    event_graph = next((graph for graph in result.graphs if graph.graph_name == "EventGraph"), result.graphs[0])
    assert event_graph.graph_guid
    assert len(event_graph.nodes) >= 1
    assert sum(len(node.pins) for node in event_graph.nodes) >= 1
    assert any(
        pin.persistent_guid is not None
        for node in event_graph.nodes
        for pin in node.pins
    )
    assert sum(
        len(getattr(pin, "linked_to_raw", []) or [])
        for graph in result.graphs
        for node in graph.nodes
        for pin in node.pins
    ) >= 1
    assert any(variable.default_value not in (None, "") for variable in result.blueprint.variables)


@pytest.mark.integration
def test_real_anim_blueprint_graph_metadata_has_standard_references(ue_sample_root: Path):
    asset = next(item for item in DIAGNOSTIC_ASSETS if item.label == "manny_combat_anim_blueprint")
    path = _asset_path(ue_sample_root, asset)
    if not path.exists():
        pytest.skip(f"sample asset not found: {path}")

    result = _parse_asset(path, tolerant=True)

    assert result.is_success, f"{path} did not parse successfully: {result.errors}"
    assert result.blueprint is not None
    assert len(result.blueprint.variables) >= 1
    assert any(variable.var_guid for variable in result.blueprint.variables)
    assert any(variable.default_value not in (None, "") for variable in result.blueprint.variables)
    assert len(result.graphs) >= 1
    graph = result.graphs[0]
    assert graph.graph_guid
    assert len(graph.nodes) >= 1
    assert sum(len(node.pins) for node in graph.nodes) >= 1
    assert any(
        pin.persistent_guid is not None
        for node in graph.nodes
        for pin in node.pins
    )
    assert sum(
        len(getattr(pin, "linked_to_raw", []) or [])
        for node in graph.nodes
        for pin in node.pins
    ) >= 1


@pytest.mark.integration
@pytest.mark.parametrize(
    ("label", "required_keys"),
    [
        ("level_proto_texture", {"parse_status", "raw_offset", "sample_size"}),
        ("manny_material_instance", {"parse_status", "raw_offset", "sample_size"}),
        ("level_proto_static_mesh", {"parse_status", "raw_offset", "sample_size"}),
    ],
)
def test_real_core_asset_metadata_fields_are_present(
    ue_sample_root: Path,
    label: str,
    required_keys: set[str],
):
    asset = next(item for item in STABLE_ASSETS if item.label == label)
    path = _asset_path(ue_sample_root, asset)
    if not path.exists():
        pytest.skip(f"sample asset not found: {path}")

    result = _parse_asset(path, tolerant=True)
    assert result.is_success, f"{path} did not parse successfully: {result.errors}"

    export = next(
        (
            export
            for export in result.export_map
            if export.object_name == path.stem and export.serial_size > 0
        ),
        None,
    )
    assert export is not None, f"no primary export found for {path.stem}"

    parsed = _parse_representative_export(path, asset.category, export, result.name_map)

    assert required_keys <= set(parsed)
    assert parsed["parse_status"] == "partial_metadata"


@pytest.mark.integration
@pytest.mark.parametrize("asset", [_param(asset) for asset in DIAGNOSTIC_ASSETS])
def test_diagnostic_blueprint_assets_do_not_crash_in_tolerant_mode(
    ue_sample_root: Path,
    asset: SampleAsset,
):
    path = _asset_path(ue_sample_root, asset)
    if not path.exists():
        pytest.skip(f"sample asset not found: {path}")

    result = _parse_asset(path, tolerant=True)

    assert result.is_success, f"{asset.category} diagnostic sample failed: {result.errors}"
    assert result.summary is not None
    assert result.linker is not None
    assert result.name_map
    assert result.export_map


def _parser_for_category(category: str) -> Callable:
    if category == "Texture2D":
        from uasset_read.parsers.asset_types.texture2d import parse_texture2d

        return parse_texture2d
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
    raise AssertionError(f"no parser configured for category: {category}")


def _parse_representative_export(path: Path, category: str, export, name_map: list[str]) -> dict:
    from uasset_read.archive import FArchive

    parser = _parser_for_category(category)
    archive = FArchive(str(path), tolerant=True)
    try:
        archive.seek(export.serial_offset + export.script_serialization_start_offset)
        return parser(archive, name_map)
    finally:
        archive.close()
