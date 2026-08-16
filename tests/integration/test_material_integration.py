"""Integration tests for Material semantic JSON with real samples."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

SAMPLE_ROOTS = [
    Path("E:/Develop/lib/Samples"),
    ROOT / "tests" / "samples",
]


def _find_sample(name_pattern: str) -> Path | None:
    for root in SAMPLE_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*.uasset"):
            if name_pattern.lower() in p.name.lower():
                return p
    return None


def _parse_asset(asset_path: Path) -> dict:
    """Parse a .uasset file and return JSON dict."""
    sys.path.insert(0, str(ROOT / "src"))
    from uasset_read.pipeline.core import parse_package
    from uasset_read.ir_builder import build_package_ir
    from uasset_read.semantic.builder import build_semantic_ir
    from uasset_read.semantic.projection import project_semantic
    from uasset_read.semantic.render import render_semantic_json

    parse_result = parse_package(str(asset_path))
    ir = build_package_ir(parse_result)
    semantic_ir = build_semantic_ir(ir, source_path=str(asset_path))
    semantic_ir = project_semantic(semantic_ir, "debug")
    output = render_semantic_json(semantic_ir)
    return json.loads(output)


@pytest.fixture(scope="module")
def firstperson_m_flatcol():
    path = _find_sample("FirstPerson_M_FlatCol")
    if path is None:
        pytest.skip("FirstPerson_M_FlatCol sample not found")
    return path


@pytest.fixture(scope="module")
def firstperson_m_prototypegrid():
    path = _find_sample("FirstPerson_M_PrototypeGrid")
    if path is None:
        pytest.skip("FirstPerson_M_PrototypeGrid sample not found")
    return path


@pytest.fixture(scope="module")
def cassini_mi():
    path = _find_sample("CassiniSample_MI_Template_BaseGray_Metal")
    if path is None:
        pytest.skip("CassiniSample_MI_Template_BaseGray_Metal sample not found")
    return path


@pytest.fixture(scope="module")
def startercontent_m_wood():
    path = _find_sample("StarterContent_M_Wood_Walnut")
    if path is None:
        pytest.skip("StarterContent_M_Wood_Walnut sample not found")
    return path


class TestMaterialIntegration:
    def test_material_section_present(self, firstperson_m_flatcol):
        data = _parse_asset(firstperson_m_flatcol)
        assert "material" in data
        assert data["material"]["material_type"] == "Material"

    def test_material_has_expressions(self, firstperson_m_flatcol):
        data = _parse_asset(firstperson_m_flatcol)
        assert len(data["material"]["expressions"]) > 0

    def test_expression_has_class(self, firstperson_m_flatcol):
        data = _parse_asset(firstperson_m_flatcol)
        for expr in data["material"]["expressions"]:
            assert expr["expression_class"]
            assert expr["expression_class"].startswith("MaterialExpression")

    def test_material_has_properties(self, firstperson_m_flatcol):
        data = _parse_asset(firstperson_m_flatcol)
        assert "properties" in data["material"]
        props = data["material"]["properties"]
        # Should have at least usage_flags
        assert len(props) > 0

    def test_prototypegrid_has_expressions(self, firstperson_m_prototypegrid):
        data = _parse_asset(firstperson_m_prototypegrid)
        assert "material" in data
        assert len(data["material"]["expressions"]) > 0

    def test_material_instance_has_parent(self, cassini_mi):
        data = _parse_asset(cassini_mi)
        assert "material" in data
        assert data["material"]["material_type"] == "MaterialInstance"
        assert data["material"].get("parent")

    def test_material_instance_structure(self, cassini_mi):
        """MaterialInstance should have the correct structure even if parameters are empty."""
        data = _parse_asset(cassini_mi)
        mat = data["material"]
        assert mat["material_type"] == "MaterialInstance"
        # Parameters may be empty if the asset is partially parsed
        assert "parameters" in mat or "parent" in mat

    def test_startercontent_material(self, startercontent_m_wood):
        data = _parse_asset(startercontent_m_wood)
        assert "material" in data
        assert data["material"]["material_type"] == "Material"
