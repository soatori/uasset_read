"""Consolidated semantic IR tests.

Tests cover: builder, kinds, IR nodes, validation, canonical sorting,
and domain extractors (one per domain).
"""
from uasset_read.semantic.ir import ContentNode
from uasset_read.semantic.kinds import AssetKind, classify_asset
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.validator import validate_semantic_ir
from uasset_read.semantic.canonical import canonical_sort
from uasset_read.semantic.graph_domain import extract_graph
from uasset_read.semantic.resource_domain import extract_resource
from uasset_read.semantic.structured_domain import extract_structured
from uasset_read.models.ir import (
    ExportIR, GraphIR, NodeIR, PinIR, PropertyIR,
)
from tests.conftest import make_package_ir, make_semantic_ir


class TestSemanticBuilder:
    """build_semantic_ir produces valid IR with correct asset kind."""

    def test_resource_asset(self):
        ir = make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.format == "uasset_read.asset_semantic"
        assert semantic.format_version == "1.0.0"
        assert semantic.asset.kind == AssetKind.RESOURCE
        assert semantic.asset.class_name == "Texture2D"
        errors = validate_semantic_ir(semantic)
        assert errors == []


class TestAssetClassification:
    """classify_asset returns the correct domain for known classes."""

    def test_graph_domain(self):
        assert classify_asset("Material", None) == AssetKind.GRAPH
        assert classify_asset("SoundCue", None) == AssetKind.GRAPH
        assert classify_asset("NiagaraSystem", None) == AssetKind.GRAPH
        assert classify_asset("StaticMesh", None) == AssetKind.STRUCTURED
        assert classify_asset("Texture2D", None) == AssetKind.RESOURCE
        assert classify_asset("SomeUnknownClass", None) == AssetKind.OPAQUE


class TestContentNode:
    """ContentNode leaf and branch creation."""

    def test_leaf_and_branch(self):
        leaf = ContentNode(key="width", value=1024)
        assert leaf.key == "width"
        assert leaf.value == 1024
        assert leaf.children is None

        branch = ContentNode(
            key="properties",
            children=[
                ContentNode(key="width", value=1024),
                ContentNode(key="height", value=512),
            ],
        )
        assert branch.children is not None
        assert len(branch.children) == 2


class TestSemanticValidation:
    """validate_semantic_ir catches invalid format strings."""

    def test_wrong_format(self):
        ir = make_semantic_ir(format="wrong")
        errors = validate_semantic_ir(ir)
        assert any("format" in e.lower() for e in errors)


class TestCanonicalSort:
    """canonical_sort orders top-level and nested keys."""

    def test_top_level_key_order(self):
        data = {
            "diagnostics": [], "asset": {}, "content": {},
            "references": [], "coverage": {},
            "format": "x", "format_version": "1", "mode": "standard",
        }
        result = canonical_sort(data)
        keys = list(result.keys())
        assert keys == [
            "format", "format_version", "mode", "asset",
            "references", "content", "coverage", "diagnostics",
        ]


class TestDomainExtractors:
    """extract_graph, extract_resource, extract_structured produce valid nodes."""

    def test_all_domains(self):
        # Resource domain
        resource_export = ExportIR(
            index=0, object_name="T_Default", object_class="Texture2D",
            serial_size=2048, outer_index_resolved=None, super_index_resolved=None,
            parent_class=None,
            properties=[
                PropertyIR(name="SizeX", type="IntProperty", value=1024, array_index=0, guid=None),
                PropertyIR(name="SizeY", type="IntProperty", value=512, array_index=0, guid=None),
            ],
            graphs=[], bulk_data=None,
            asset_type_data={"parse_status": "partial_metadata", "raw_offset": 100, "sample_size": 256},
        )
        rn = extract_resource(resource_export)
        assert rn.key == "root"
        rc = {c.key: c for c in (rn.children or [])}
        assert rc["class_name"].value == "Texture2D"
        assert rc["serial_size"].value == 2048

        # Structured domain
        structured_export = ExportIR(
            index=0, object_name="SK_Default", object_class="Skeleton",
            serial_size=8192, outer_index_resolved=None, super_index_resolved=None,
            parent_class=None, properties=[], graphs=[], bulk_data=None,
            asset_type_data={
                "parse_status": "success",
                "reference_skeleton": {
                    "names": ["root", "spine", "head"],
                    "parents": [-1, 0, 1],
                    "bone_count": 3,
                },
                "retarget_source_count": 0,
            },
        )
        sn = extract_structured(structured_export)
        assert sn.key == "root"
        sc = {c.key: c for c in (sn.children or [])}
        assert sc["class_name"].value == "Skeleton"
        assert "reference_skeleton" in sc

        # Graph domain
        graph = GraphIR(
            graph_guid="00000000000000000000000000000001",
            graph_name="SoundCueGraph", graph_class="EdGraph",
            nodes=[
                NodeIR(
                    node_guid="0000000000000000000000000000abc1",
                    node_class="SoundCueNode_Mixer", node_comment=None,
                    pins=[PinIR(pin_name="Output", pin_type="exec", linked_to=[], direction="EGPD_Output", default_value=None)],
                    execution_flow=[],
                ),
            ],
            execution_chains=[],
        )
        graph_export = ExportIR(
            index=0, object_name="SFX_Explosion", object_class="SoundCue",
            serial_size=2048, outer_index_resolved=None, super_index_resolved=None,
            parent_class=None,
            properties=[
                PropertyIR(name="VolumeMultiplier", type="FloatProperty", value=0.8, array_index=0, guid=None),
            ],
            graphs=[graph], bulk_data=None,
            asset_type_data={"parse_status": "success", "first_node": 1, "volume_multiplier": 0.8},
        )
        gn = extract_graph(graph_export)
        assert gn.key == "root"
        gc = {c.key: c for c in (gn.children or [])}
        assert gc["class_name"].value == "SoundCue"
        assert "graphs" in gc
