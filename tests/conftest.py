"""Shared test fixtures and factory helpers for uasset_read test suite."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Path fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def samples_dir() -> Path:
    """Path to the tests/samples/ directory containing real .uasset files."""
    return Path(__file__).parent / "samples"


@pytest.fixture
def sample_uassets(samples_dir: Path) -> list[Path]:
    """List of all .uasset sample files."""
    return sorted(samples_dir.glob("*.uasset"))


@pytest.fixture
def sample_umaps(samples_dir: Path) -> list[Path]:
    """List of all .umap sample files."""
    return sorted(samples_dir.glob("*.umap"))


# ---------------------------------------------------------------------------
# Category-based sample grouping
# ---------------------------------------------------------------------------

_SAMPLE_CATEGORIES = {
    "blueprint": [
        "FirstPerson_BP_FirstPersonCharacter",
        "FirstPerson_BP_FirstPersonGameMode",
        "StackOBot_BP_Drone",
        "StackOBot_GI_StackOBot",
        "IntroToUnreal_BP_Light",
        "IntroToUnreal_BP_SaveData",
        "NM_BPSystemEvent",
    ],
    "anim_blueprint": [
        "ABP_RifleAnimLayers",
        "ALS_AnimBP",
    ],
    "material": [
        "FirstPerson_M_FlatCol",
        "FirstPerson_M_PrototypeGrid",
        "StackOBot_M_BotBase",
        "StarterContent_M_Wood_Walnut",
        "IntroToUnreal_M_Plastic",
        "CassiniSample_MI_Template_BaseGray_Metal",
    ],
    "skeleton": [
        "ALS_Mannequin_Skeleton",
    ],
    "animation": [
        "ALS_CLF_GetUp_Back_Montage_Default",
        "ALS_N_FallLoop",
        "Lyra_AnimStruct_CardinalDirections",
    ],
    "data_table": [
        "ALS_FootstepDataTable",
        "FirstPerson_DT_WeaponList",
    ],
    "enum": [
        "Lyra_Enum_PanelType",
        "StackOBot_Enum_CameraState",
    ],
    "texture": [
        "FirstPerson_T_GridChecker_A",
    ],
    "static_mesh": [
        "StarterContent_SM_Chair",
    ],
    "sound": [
        "ALS_Concrete_Step_01_SoundWave",
        "CropoutSample_Attenuation_general",
        "StarterContent_Starter_Background_Cue",
    ],
    "other": [
        "CiciToon_SK_Mannequin",
        "Lyra_B_Rifle",
        "Lyra_Curve_LaunchpadMaterialEffect",
        "Lyra_SEQ_LobbyScreen_LevelSequence",
        "Echo_calf_l_PoseAsset",
        "FirstPersonC_Variant_Shooter_CubeBuilder_4",
        "GameAnimSample_FaceArchetype_LODSettings_High",
        "GameAnimSample_SandboxAnimCurveCompSettings",
        "GameAnimSample_TeethSubsurfaceProfile",
        "MutableSample_GrayLightTextureCube",
        "ProjectTitan_SM_GrassBlade_FoliageType",
        "StackOBot_Struct_Objective",
    ],
}


def get_samples_by_category(samples_dir: Path, category: str) -> list[Path]:
    """Return sample paths for a given category name."""
    stems = _SAMPLE_CATEGORIES.get(category, [])
    result = []
    for stem in stems:
        p = samples_dir / f"{stem}.uasset"
        if p.exists():
            result.append(p)
    return result


def get_all_categorized_samples(samples_dir: Path) -> list[Path]:
    """Return all categorized sample paths (deduplicated, sorted)."""
    seen: set[str] = set()
    result: list[Path] = []
    for stems in _SAMPLE_CATEGORIES.values():
        for stem in stems:
            if stem not in seen:
                seen.add(stem)
                p = samples_dir / f"{stem}.uasset"
                if p.exists():
                    result.append(p)
    return sorted(result, key=lambda p: p.name)


# ---------------------------------------------------------------------------
# Lightweight IR factory helpers (for unit tests without file I/O)
# ---------------------------------------------------------------------------

def make_minimal_parse_result(**overrides: Any) -> Any:
    """Build a minimal ParseResult for unit tests that don't need real parsing.

    Returns a dict-like object with the required fields.
    """
    from uasset_read.models.result import ParseResult

    result = ParseResult()
    result.is_success = True
    for k, v in overrides.items():
        setattr(result, k, v)
    return result
