# tests/test_constructor_metadata.py
"""变量分类测试 — 验证 PackageIR.variables 不包含元数据变量。"""
from __future__ import annotations

import os

import pytest

_REAL_BLUEPRINT = os.path.join(
    os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\Samples"),
    "FirstPerson", "Content", "FirstPerson", "Blueprints",
    "BP_FirstPersonCharacter.uasset",
)

_has_real_asset = os.path.isfile(_REAL_BLUEPRINT)

# 已知元数据键（不应出现在构造函数中）
_METADATA_KEYS = {
    "BlueprintSystemVersion",
    "GeneratedClass",
    "SimpleConstructionScript",
    "bCanEverTick",
    "bCanEverRender",
}


@pytest.mark.integration
@pytest.mark.quality
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestVariableClassification:
    """验证 PackageIR.variables 不包含元数据变量。"""

    def test_no_metadata_variables_in_ir(self):
        """PackageIR.variables 不应包含 BlueprintSystemVersion 等。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        from uasset_read.ir_builder import build_package_ir

        result = parse_uasset_with_linker(_REAL_BLUEPRINT, tolerant=True)
        ir = build_package_ir(result)

        var_names = {v.name for v in ir.variables}
        metadata_found = var_names & _METADATA_KEYS
        assert len(metadata_found) == 0, (
            f"PackageIR.variables 包含元数据变量: {metadata_found}"
        )
