"""Regression coverage for #517 asset-class export metadata."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from uasset_read.ir_builder import _build_export_ir
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.serializers.object_resources import (
    ObjectExport,
    ObjectImport,
    PackageIndex,
)


_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "package.schema.json"


def _import(name: str) -> ObjectImport:
    return ObjectImport(
        class_package="/Script/Engine",
        class_name="Class",
        outer_index=PackageIndex(0),
        object_name=name,
    )


def _export(
    name: str,
    class_index: int,
    *,
    outer_index: int = 0,
    is_asset: bool = False,
) -> ObjectExport:
    return ObjectExport(
        class_index=PackageIndex(class_index),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(outer_index),
        object_name=name,
        object_flags=0,
        serial_size=1,
        serial_offset=0,
        b_is_asset=is_asset,
    )


def _result(exports: list[ObjectExport]) -> SimpleNamespace:
    return SimpleNamespace(
        blueprint=None,
        linker=None,
        import_map=[
            _import("StaticMesh"),
            _import("BodySetup"),
            _import("SkeletalMesh"),
            _import("FbxSkeletalMeshImportData"),
        ],
        export_map=exports,
    )


def _render(exports: list[SimpleNamespace], output_level: str) -> dict:
    header = SimpleNamespace(
        package_name="/Game/TestAsset",
        package_class="",
        package_flags=0,
        total_export_count=len(exports),
        total_import_count=0,
        ue_version="5.8",
        saved_hash=None,
        total_properties=0,
        total_name_entries=0,
    )
    ir = SimpleNamespace(
        header=header,
        diagnostics_data=None,
        exports=exports,
        import_map=[],
        name_map_entries=[],
        name_map=(),
        blueprint=None,
        decompiled_functions=[],
        execution_chains=[],
        variables=[],
        dependencies=None,
        logic_sources=[],
        diagnostics=[],
        animation=None,
        debug=None,
        function_graphs=[],
        statistics={},
    )
    return json.loads(JSONRenderer().render(ir, RenderOptions(output_level=output_level)))


def _render_export(name: str, asset_class: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        object_name=name,
        object_class="BodySetup",
        asset_class=asset_class,
        serial_size=1,
        parent_class=None,
        properties=[],
        graphs=[],
        parse_status="success",
        fallback_reason=None,
        error_message=None,
        asset_type_data=None,
    )


def test_asset_class_follows_each_export_nearest_asset_ancestor() -> None:
    static_root = _export("SM_Rifle", -1, is_asset=True)
    static_child = _export("BodySetup_1", -2, outer_index=1)
    skeletal_root = _export("SKM_Rifle", -3, is_asset=True)
    skeletal_child = _export("FbxSkeletalMeshImportData_1", -4, outer_index=3)
    result = _result([static_root, static_child, skeletal_root, skeletal_child])

    static_root_ir = _build_export_ir(0, static_root, result)
    static_child_ir = _build_export_ir(1, static_child, result)
    skeletal_root_ir = _build_export_ir(2, skeletal_root, result)
    skeletal_child_ir = _build_export_ir(3, skeletal_child, result)

    assert (static_root_ir.object_class, static_root_ir.asset_class) == (
        "StaticMesh",
        "StaticMesh",
    )
    assert (static_child_ir.object_class, static_child_ir.asset_class) == (
        "BodySetup",
        "StaticMesh",
    )
    assert (skeletal_root_ir.object_class, skeletal_root_ir.asset_class) == (
        "SkeletalMesh",
        "SkeletalMesh",
    )
    assert (skeletal_child_ir.object_class, skeletal_child_ir.asset_class) == (
        "FbxSkeletalMeshImportData",
        "SkeletalMesh",
    )


def test_asset_class_is_unavailable_for_missing_invalid_or_cyclic_ownership() -> None:
    no_root = _export("Orphan", -2)
    invalid_outer = _export("InvalidOuter", -2, outer_index=99)
    cyclic_outer = _export("CyclicOuter", -2, outer_index=3)
    unresolved_root = _export("UnknownAsset", -99, is_asset=True)
    result = _result([no_root, invalid_outer, cyclic_outer, unresolved_root])

    assert _build_export_ir(0, no_root, result).asset_class is None
    assert _build_export_ir(1, invalid_outer, result).asset_class is None
    assert _build_export_ir(2, cyclic_outer, result).asset_class is None
    assert _build_export_ir(3, unresolved_root, result).asset_class is None


def test_asset_class_json_output_level_contract() -> None:
    exports = [
        _render_export("BodySetup_1", "StaticMesh"),
        _render_export("Orphan", None),
    ]

    standard = _render(exports, "standard")
    debug = _render(exports, "debug")

    assert standard["exports"][0]["asset_class"] == "StaticMesh"
    assert "asset_class" not in standard["exports"][1]
    assert debug["exports"][0]["asset_class"] == "StaticMesh"
    assert debug["exports"][1]["asset_class"] is None


def test_schema_documents_optional_asset_class() -> None:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["$defs"]["ExportEntry"]["properties"]["asset_class"] == {
        "type": ["string", "null"],
        "description": "Owning asset class resolved from the nearest asset export",
    }
