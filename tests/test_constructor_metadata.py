# tests/test_constructor_metadata.py
"""构造函数元数据过滤测试 — 验证 BlueprintSystemVersion 等不注入构造函数。"""
from __future__ import annotations

import os
import re

import pytest

from uasset_read.core import parse_single

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


@pytest.fixture(scope="module")
def cpp_output() -> str:
    return parse_single(_REAL_BLUEPRINT, format="cpp_skeleton", tolerant=True)


@pytest.mark.integration
@pytest.mark.quality
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestConstructorMetadataFilter:
    """验证构造函数不注入元数据变量。"""

    def test_no_blueprint_system_version(self, cpp_output: str):
        """构造函数不应包含 BlueprintSystemVersion 赋值。"""
        assert "BlueprintSystemVersion" not in cpp_output

    def test_no_generated_class_assignment(self, cpp_output: str):
        """构造函数不应包含 GeneratedClass 赋值。"""
        assert "GeneratedClass = " not in cpp_output

    def test_no_metadata_keys_in_constructor(self, cpp_output: str):
        """构造函数不应包含任何已知元数据键。"""
        # 提取构造函数部分
        ctor_match = re.search(
            r'::\w+\(\)\s*:\s*(.*?)(?=\nvoid|\n\n|$)',
            cpp_output,
            re.DOTALL,
        )
        if ctor_match:
            ctor_body = ctor_match.group(1)
            for key in _METADATA_KEYS:
                assert key not in ctor_body, f"构造函数包含元数据键: {key}"


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
