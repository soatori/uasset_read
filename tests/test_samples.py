"""Real-sample evidence for capabilities the project currently claims."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

import pytest


SAMPLES = Path(__file__).parent / "samples"
MANIFEST = SAMPLES / "manifest.json"
CAPABILITIES = (
    ("ALS_FootstepDataTable.uasset", "DataTable", {"kind": "data_table"}),
    ("Lyra_Enum_PanelType.uasset", "UserDefinedEnum", {"kind": "user_defined_enum", "enum_name": "Enum_PanelType"}),
    (
        "StackOBot_Struct_Objective.uasset",
        "UserDefinedStruct",
        {"kind": "user_defined_struct", "struct_name": "Struct_Objective"},
    ),
    ("FirstPerson_T_GridChecker_A.uasset", "Texture2D", {"kind": "texture", "texture_type": "Texture2D"}),
    (
        "MutableSample_GrayLightTextureCube.uasset",
        "TextureCube",
        {"kind": "texture", "texture_type": "TextureCube"},
    ),
    ("ALS_Concrete_Step_01_SoundWave.uasset", "SoundWave", {"kind": "sound", "sound_type": "SoundWave"}),
    ("ALS_Mannequin_Skeleton.uasset", "Skeleton", {"kind": "skeleton"}),
    ("StarterContent_SM_Chair.uasset", "StaticMesh", {"kind": "mesh", "mesh_type": "StaticMesh"}),
    ("FirstPerson_M_PrototypeGrid.uasset", "Material", {"kind": "material"}),
    (
        "CassiniSample_MI_Template_BaseGray_Metal.uasset",
        "MaterialInstanceConstant",
        {"kind": "material_instance"},
    ),
    ("StackOBot_BP_Drone.uasset", "BlueprintGeneratedClass", {"kind": "blueprint"}),
    ("ABP_RifleAnimLayers.uasset", "AnimBlueprintGeneratedClass", {"kind": "anim_blueprint"}),
    ("NM_BPSystemEvent.uasset", "NiagaraGraph", {"kind": "niagara", "niagara_type": "NiagaraGraph"}),
    ("NM_BPSystemEvent.uasset", "NiagaraScript", {"kind": "niagara", "niagara_type": "NiagaraScript"}),
    ("NM_BPSystemEvent.uasset", "NiagaraScriptSource", {"kind": "niagara", "niagara_type": "NiagaraScriptSource"}),
    ("NM_BPSystemEvent.uasset", "NiagaraNodeOutput", {"kind": "niagara", "niagara_type": "NiagaraNodeOutput"}),
    ("NM_BPSystemEvent.uasset", "NiagaraNodeSelect", {"kind": "niagara", "niagara_type": "NiagaraNodeSelect"}),
    ("NM_BPSystemEvent.uasset", "NiagaraNodeStaticSwitch", {"kind": "niagara", "niagara_type": "NiagaraNodeStaticSwitch"}),
)


@lru_cache(maxsize=None)
def _asset_document(sample: str):
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(SAMPLES / sample, depth="asset")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_manifest_matches_every_real_sample():
    """The retained real-sample corpus must match its review-controlled manifest exactly."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected_files = {entry["name"] for entry in manifest["samples"]}
    actual_files = {path.name for path in SAMPLES.iterdir() if path.suffix in {".uasset", ".umap", ".utoc", ".ucas", ".pak"}}
    assert manifest["summary"]["total_samples"] == len(manifest["samples"]) == 48
    assert actual_files == expected_files
    for entry in manifest["samples"]:
        path = SAMPLES / entry["name"]
        assert path.stat().st_size == entry["size_bytes"], entry["name"]
        assert _sha256(path) == entry["sha256"], entry["name"]


@pytest.mark.parametrize(("sample", "class_name", "expected"), CAPABILITIES, ids=[item[1] for item in CAPABILITIES])
def test_real_sample_proves_claimed_capability(sample: str, class_name: str, expected: dict[str, object]):
    """Each claimed capability must produce stable semantics from a real fixture."""
    obj = next(item for item in _asset_document(sample).objects if item.class_name == class_name)
    assert obj.status.semantic == "complete"
    assert obj.coverage
    assert {key: obj.semantic[key] for key in expected} == expected

    if class_name == "DataTable":
        assert obj.semantic["row_count"] >= 0
    elif class_name == "Skeleton":
        assert obj.semantic["bone_count"] == len(obj.semantic["bones"]) > 0
    elif class_name == "StaticMesh":
        assert obj.semantic["lod_count"] == len(obj.semantic["lods"])
    elif class_name in {"BlueprintGeneratedClass", "AnimBlueprintGeneratedClass"}:
        assert not {"nodes", "bytecode", "graph"} & obj.semantic.keys()
