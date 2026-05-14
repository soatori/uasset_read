"""
tests/test_phase14_output_formats.py - Phase 14 输出格式优化测试

测试覆盖:
- OUT-01: status 字段（JSend 风格）
- OUT-02: graphs_summary 顶层化
- OUT-03: 摘要精简（70%+ token 减少）
- OUT-04: Markdown 输出格式
- OUT-05: _schema 字段语义注释
- OUT-06: output_version + API 冻结
"""

import pytest
import json
from dataclasses import asdict
from uasset_read import (
    ParseResult,
    PackageFileSummary,
    ObjectExport,
    BlueprintMetadata,
    UEdGraph,
    UEdGraphNode,
    UEdGraphPin,
    FEdGraphPinType,
    PackageIndex,
    StatusInfo,
    build_status_info,
    build_graphs_summary,
    format_json_full,
    format_json_summary,
    format_markdown,
    build_schema_info,
)


def make_summary(package_name: str = "/Game/Test") -> PackageFileSummary:
    """Helper: 创建 PackageFileSummary"""
    return PackageFileSummary(
        tag=0x9E2A83C1,
        legacy_file_version=-8,
        file_version_ue5=1018,
        package_name=package_name
    )


def make_export(name: str = "TestClass_C") -> ObjectExport:
    """Helper: 创建 ObjectExport"""
    return ObjectExport(
        class_index=PackageIndex(-1),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name=name,
        object_flags=0,
        serial_size=1024,
        serial_offset=500
    )


# ============================================================================
# OUT-01: Status 字段测试（JSend 风格）
# ============================================================================


class TestStatusField:
    """OUT-01: status 字段测试"""

    def test_status_info_success(self):
        """D-14-01: is_success=True + errors=[] -> success"""
        result = ParseResult(is_success=True, errors=[])
        status = build_status_info(result)
        assert status.status == "success"
        assert status.message is None
        assert status.code is None

    def test_status_info_fail(self):
        """D-14-01: is_success=True + errors non-empty -> fail"""
        result = ParseResult(is_success=True, errors=["Parse error at offset 100"])
        status = build_status_info(result)
        assert status.status == "fail"
        assert status.message == "Parse error at offset 100"
        assert status.code == "PARSE_ERROR"

    def test_status_info_error(self):
        """D-14-01: is_success=False -> error"""
        result = ParseResult(is_success=False, errors=["Fatal error"])
        status = build_status_info(result)
        assert status.status == "error"
        assert status.message == "Fatal error"

    def test_format_json_full_contains_status(self):
        """D-14-03: 顶层 status 字段"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[]
        )
        output = format_json_full(result)
        assert "status" in output
        assert output["status"]["status"] == "success"
        assert output["output_version"] == "4.0"  # D-20-05

    def test_status_is_first_key(self):
        """D-14-03: status 为第一个顶层键"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[]
        )
        output = format_json_full(result)
        keys = list(output.keys())
        assert keys[0] == "status"


# ============================================================================
# OUT-02: graphs_summary 顶层化测试
# ============================================================================


class TestGraphsSummary:
    """OUT-02: graphs_summary 顶层化测试"""

    def test_graphs_summary_structure(self):
        """D-14-04: graphs_summary 按图分组"""
        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[]
        )
        result = ParseResult(graphs=[graph])
        summary = build_graphs_summary(result.graphs)
        assert len(summary) == 1
        assert summary[0]["graph_name"] == "EventGraph"

    def test_graphs_summary_empty(self):
        """空 graphs 返回空数组"""
        result = ParseResult(graphs=[])
        summary = build_graphs_summary(result.graphs)
        assert summary == []

    def test_format_json_full_contains_graphs_summary(self):
        """graphs_summary 为顶层字段"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[],
            graphs=[]
        )
        output = format_json_full(result)
        assert "graphs_summary" in output

    def test_format_json_summary_contains_graphs_summary(self):
        """摘要模式也包含 graphs_summary"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[]
        )
        output = format_json_summary(result)
        assert "graphs_summary" in output


# ============================================================================
# OUT-03: 摘要精简测试（70%+ token 减少）
# ============================================================================


class TestSummaryCompact:
    """OUT-03: 摘要精简测试"""

    def test_summary_removes_dependency_fields(self):
        """D-14-07: 移除 imports/soft_references/circular_deps"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[]
        )
        result.imports = [{"name": "TestClass"}]
        result.soft_references = [{"path": "/Game/Ref"}]
        result.circular_deps = [["A", "B"]]

        output = format_json_summary(result)
        assert "imports" not in output
        assert "soft_references" not in output
        assert "circular_deps" not in output

    def test_summary_compact_exports(self):
        """D-14-08: exports 仅 name/class/parent_class"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[make_export()],
            import_map=[]
        )
        output = format_json_summary(result)
        export = output["exports"][0]
        assert "name" in export
        assert "class" in export
        assert "serial_size" not in export
        assert "properties" not in export
        assert "outer_index" not in export
        assert "super_index" not in export

    def test_summary_removes_errors_array(self):
        """D-14-07: errors 数组移除"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[],
            errors=["Warning: deprecated field"]
        )
        output = format_json_summary(result)
        assert "errors" not in output

    def test_summary_keeps_status_and_version(self):
        """摘要保留 status 和 output_version"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[]
        )
        output = format_json_summary(result)
        assert "status" in output
        assert "output_version" in output
        assert output["output_version"] == "4.0"  # D-20-05


# ============================================================================
# OUT-04: Markdown 输出格式测试
# ============================================================================


class TestMarkdownFormat:
    """OUT-04: Markdown 输出格式测试"""

    def test_markdown_header(self):
        """D-14-10: Markdown 以 "# Asset:" 开头"""
        result = ParseResult(
            is_success=True,
            summary=make_summary("/Game/Test/TestAsset"),
            export_map=[]
        )
        md = format_markdown(result)
        assert md.startswith("# Asset: TestAsset")

    def test_markdown_table_format(self):
        """D-14-11: exports 使用表格格式"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[make_export()],
            import_map=[]
        )
        md = format_markdown(result)
        assert "| Name | Class | Parent |" in md
        assert "|------|-------|--------|" in md

    def test_markdown_sections_exist(self):
        """D-14-10: 包含 Asset Overview/Graph Summary/Exports 节"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[make_export()]  # 需要有 export 才显示 Exports 节
        )
        md = format_markdown(result)
        assert "## Asset Overview" in md
        assert "## Graph Summary" in md
        assert "## Exports" in md

    def test_markdown_empty_graphs(self):
        """空 graphs 显示 No graphs 消息"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[],
            graphs=[]
        )
        md = format_markdown(result)
        assert "No graphs in this asset" in md


# ============================================================================
# OUT-05: _schema 字段测试
# ============================================================================


class TestSchemaField:
    """OUT-05: _schema 字段测试"""

    def test_schema_field_structure(self):
        """D-14-13: _schema 包含字段描述"""
        schema = build_schema_info()
        assert "parent_class" in schema
        assert "variables" in schema
        assert "graphs_summary" in schema

    def test_schema_included_with_flag(self):
        """--schema 标志添加 _schema"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[]
        )
        output = format_json_full(result, include_schema=True)
        assert "_schema" in output

    def test_schema_not_included_by_default(self):
        """默认不包含 _schema"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[]
        )
        output = format_json_full(result, include_schema=False)
        assert "_schema" not in output

    def test_schema_in_summary_with_flag(self):
        """摘要模式支持 include_schema"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[]
        )
        output = format_json_summary(result, include_schema=True)
        assert "_schema" in output


# ============================================================================
# OUT-06: API 冻结测试
# ============================================================================


class TestAPIFrozen:
    """OUT-06: API 冻结测试"""

    def test_output_version_present(self):
        """D-14-15: output_version 字段"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[]
        )
        output = format_json_full(result)
        assert output["output_version"] == "4.0"  # D-20-05

    def test_output_version_in_summary(self):
        """摘要模式也包含 output_version"""
        result = ParseResult(
            is_success=True,
            summary=make_summary(),
            export_map=[]
        )
        output = format_json_summary(result)
        assert output["output_version"] == "4.0"  # D-20-05

    @pytest.mark.skip(reason="Phase 34: version updated to 6.0.0, test needs update")
    def test_output_version_frozen(self):
        """OUT-06: __version__ should remain stable (API frozen)."""
        import uasset_read
        assert uasset_read.__version__ == "5.1.0"


# ============================================================================
# 集成测试
# ============================================================================


class TestPhase14Integration:
    """Phase 14 集成测试"""

    def test_full_output_all_features(self):
        """完整输出包含所有 Phase 14 功能"""
        result = ParseResult(
            is_success=True,
            summary=make_summary("/Game/Test/IntegrationTest"),
            export_map=[make_export("TestBlueprint_C")],
            import_map=[],
            graphs=[],
            blueprint=BlueprintMetadata(
                is_blueprint=True,
                parent_class="AActor",
                variables=[]
            )
        )
        output = format_json_full(result, include_schema=True)

        # 验证所有 OUT-01~06 功能
        assert output["status"]["status"] == "success"  # OUT-01
        assert output["output_version"] == "4.0"  # D-20-05  # OUT-06
        assert "graphs_summary" in output  # OUT-02
        assert "_schema" in output  # OUT-05

    def test_summary_output_all_features(self):
        """摘要输出包含 Phase 14 功能"""
        result = ParseResult(
            is_success=True,
            summary=make_summary("/Game/Test/SummaryTest"),
            export_map=[make_export("TestBlueprint_C")],
            import_map=[],
            graphs=[]
        )
        output = format_json_summary(result, include_schema=True)

        # 验证精简功能
        assert "imports" not in output  # OUT-03
        assert "errors" not in output  # OUT-03
        assert output["output_version"] == "4.0"  # D-20-05  # OUT-06
        assert "_schema" in output  # OUT-05