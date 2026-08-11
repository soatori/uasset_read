"""Tests for Semantic IR dataclasses."""
from uasset_read.semantic.ir import (
    SemanticIR, AssetMeta, ReferenceEntry, CoverageInfo,
    DiagnosticEntry, ContentNode,
)
from uasset_read.semantic.kinds import AssetKind


class TestAssetMeta:
    def test_create_minimal(self):
        meta = AssetMeta(
            kind=AssetKind.RESOURCE,
            class_name="Texture2D",
            object_name="T_Default",
        )
        assert meta.kind == AssetKind.RESOURCE
        assert meta.class_name == "Texture2D"
        assert meta.object_name == "T_Default"
        assert meta.parse_status == "success"

    def test_create_with_all_fields(self):
        meta = AssetMeta(
            kind=AssetKind.GRAPH,
            class_name="Material",
            object_name="M_Default",
            package_path="/Game/Materials/M_Default",
            parse_status="partial",
        )
        assert meta.package_path == "/Game/Materials/M_Default"
        assert meta.parse_status == "partial"


class TestReferenceEntry:
    def test_create(self):
        ref = ReferenceEntry(
            index=0,
            kind="import",
            class_name="Texture2D",
            object_name="T_Default",
            package_path="/Game/Textures/T_Default",
        )
        assert ref.index == 0
        assert ref.kind == "import"
        assert ref.class_name == "Texture2D"


class TestCoverageInfo:
    def test_create(self):
        cov = CoverageInfo(
            fields_expected=10,
            fields_parsed=8,
            coverage_pct=80.0,
            unparsed_fields=["CustomData", "BulkData"],
        )
        assert cov.coverage_pct == 80.0
        assert len(cov.unparsed_fields) == 2


class TestDiagnosticEntry:
    def test_create(self):
        diag = DiagnosticEntry(
            severity="warning",
            code="PARTIAL_PARSE",
            message="Some fields skipped",
        )
        assert diag.severity == "warning"
        assert diag.code == "PARTIAL_PARSE"


class TestContentNode:
    def test_create_leaf(self):
        node = ContentNode(key="width", value=1024)
        assert node.key == "width"
        assert node.value == 1024
        assert node.children is None

    def test_create_branch(self):
        node = ContentNode(
            key="properties",
            children=[
                ContentNode(key="width", value=1024),
                ContentNode(key="height", value=512),
            ],
        )
        assert node.children is not None
        assert len(node.children) == 2


class TestSemanticIR:
    def test_create_minimal(self):
        ir = SemanticIR(
            format="uasset_read.asset_semantic",
            format_version="1.0.0",
            mode="standard",
            asset=AssetMeta(
                kind=AssetKind.OPAQUE,
                class_name="Unknown",
                object_name="Unknown",
            ),
            references=[],
            content=ContentNode(key="root", children=[]),
            coverage=CoverageInfo(
                fields_expected=0,
                fields_parsed=0,
                coverage_pct=0.0,
                unparsed_fields=[],
            ),
            diagnostics=[],
        )
        assert ir.format == "uasset_read.asset_semantic"
        assert ir.format_version == "1.0.0"
        assert ir.mode == "standard"
        assert ir.asset.kind == AssetKind.OPAQUE

    def test_create_full(self):
        ir = SemanticIR(
            format="uasset_read.asset_semantic",
            format_version="1.0.0",
            mode="debug",
            asset=AssetMeta(
                kind=AssetKind.STRUCTURED,
                class_name="DataTable",
                object_name="DT_Config",
            ),
            references=[
                ReferenceEntry(
                    index=0,
                    kind="import",
                    class_name="DataTable",
                    object_name="DT_Config",
                    package_path="/Game/Data/DT_Config",
                ),
            ],
            content=ContentNode(
                key="root",
                children=[
                    ContentNode(key="row_count", value=42),
                ],
            ),
            coverage=CoverageInfo(
                fields_expected=5,
                fields_parsed=5,
                coverage_pct=100.0,
                unparsed_fields=[],
            ),
            diagnostics=[],
        )
        assert ir.mode == "debug"
        assert len(ir.references) == 1
        assert ir.coverage.coverage_pct == 100.0
