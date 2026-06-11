"""P2 Post-process stage 隔离性测试 (#115)。"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from uasset_read.post_process import (
    PostProcessContext,
    PostProcessPipeline,
    GraphExtractionStage,
    BlueprintMetadataStage,
    KismetDecompileStage,
    ComponentExtractionStage,
    DependencyAnalysisStage,
    ConsistencyCheckStage,
    ParentAssetStage,
    build_default_pipeline,
)


class TestPipelineIsolation:
    """验证单个 stage 失败不阻断后续 stage。"""

    def _make_ctx(self):
        archive = MagicMock()
        summary = MagicMock()
        summary.name_count = 1
        return PostProcessContext(
            path="test.uasset",
            archive=archive,
            summary=summary,
            name_map=["test"],
            import_map=[],
            export_map=[],
            result=MagicMock(),
            tolerant=True,
        )

    def test_failing_stage_doesnt_block_others(self):
        """一个 stage 抛异常时，后续 stage 仍然执行。"""
        pipeline = PostProcessPipeline()

        stage2_called = False

        class FailingStage:
            def run(self, ctx):
                raise RuntimeError("intentional failure")

        class SuccessStage:
            def run(self, ctx):
                nonlocal stage2_called
                stage2_called = True

        pipeline.add_stage(FailingStage())
        pipeline.add_stage(SuccessStage())

        ctx = self._make_ctx()
        ctx.result.errors = []
        ctx.result.warnings = []

        pipeline.execute(ctx)

        assert stage2_called, "第二 stage 应该在第一个 stage 失败后仍被调用"

    def test_pipeline_error_reporting_parse_error_to_warnings(self):
        """ParseError 也被 execute() 捕获并写入 result.warnings（所有异常统一处理）。"""
        pipeline = PostProcessPipeline()

        class ParseErrorStage:
            def run(self, ctx):
                from uasset_read.exceptions import ParseError
                raise ParseError("test parse error")

        pipeline.add_stage(ParseErrorStage())

        ctx = self._make_ctx()
        ctx.result.errors = []
        ctx.result.warnings = []
        ctx.summary.name_count = 1

        pipeline.execute(ctx)

        # execute() 捕获所有异常并写入 warnings
        assert len(ctx.result.warnings) > 0
        assert any("error" in e.lower() for e in ctx.result.warnings)

    def test_pipeline_error_reporting_generic_to_warnings(self):
        """非 ParseError 异常写入 result.warnings。"""
        pipeline = PostProcessPipeline()

        class RuntimeErrorStage:
            def run(self, ctx):
                raise RuntimeError("intentional error")

        pipeline.add_stage(RuntimeErrorStage())

        ctx = self._make_ctx()
        ctx.result.errors = []
        ctx.result.warnings = []

        pipeline.execute(ctx)

        # 非 ParseError 异常写入 warnings
        assert len(ctx.result.warnings) > 0
        assert any("RuntimeErrorStage" in e for e in ctx.result.warnings)

    def test_default_pipeline_has_all_stages(self):
        """默认管线包含 7 个 stage。"""
        pipeline = build_default_pipeline()
        assert len(pipeline.stages) == 7
        names = [type(s).__name__ for s in pipeline.stages]
        assert "GraphExtractionStage" in names
        assert "BlueprintMetadataStage" in names
        assert "KismetDecompileStage" in names
        assert "ParentAssetStage" in names
        assert "ComponentExtractionStage" in names
        assert "DependencyAnalysisStage" in names
        assert "ConsistencyCheckStage" in names

    def test_consistency_check_sets_is_success(self):
        """ConsistencyCheckStage 设置 is_success。"""
        stage = ConsistencyCheckStage()
        ctx = self._make_ctx()
        ctx.result.errors = []
        ctx.result.name_map = ["test"]
        ctx.summary.name_count = 1

        stage.run(ctx)
        assert ctx.result.is_success is True

    def test_consistency_check_detects_empty_name_map(self):
        """ConsistencyCheckStage 检测空 name_map。"""
        stage = ConsistencyCheckStage()
        ctx = self._make_ctx()
        ctx.result.errors = []
        ctx.result.name_map = []
        ctx.summary.name_count = 5

        stage.run(ctx)
        assert ctx.result.is_success is False
        assert any("name_map" in e for e in ctx.result.errors)

    def test_multiple_failures_reported(self):
        """多个 stage 失败时，所有错误都被记录（errors + warnings）。"""
        pipeline = PostProcessPipeline()

        class ErrorStage1:
            def run(self, ctx):
                raise RuntimeError("error one")

        class ErrorStage2:
            def run(self, ctx):
                raise ValueError("error two")

        class SuccessStage:
            def run(self, ctx):
                pass

        pipeline.add_stage(ErrorStage1())
        pipeline.add_stage(ErrorStage2())
        pipeline.add_stage(SuccessStage())

        ctx = self._make_ctx()
        ctx.result.errors = []
        ctx.result.warnings = []

        pipeline.execute(ctx)

        # 两个 Runtime/ValueError 都应记录到 warnings
        assert len(ctx.result.warnings) >= 2

    def test_exceptions_in_pipeline_still_continue(self):
        """任意异常类型都不会阻断 pipeline。"""
        pipeline = PostProcessPipeline()

        called_after_error = False

        class ErrorStage:
            def run(self, ctx):
                raise KeyError("missing key")

        class ContinueStage:
            def run(self, ctx):
                nonlocal called_after_error
                called_after_error = True

        pipeline.add_stage(ErrorStage())
        pipeline.add_stage(ContinueStage())

        ctx = self._make_ctx()
        ctx.result.errors = []
        ctx.result.warnings = []

        pipeline.execute(ctx)

        assert called_after_error, "异常后 stage 应继续执行"

    def test_graph_extraction_stage_runs(self):
        """GraphExtractionStage 正常运行（无 graph 模块时静默跳过）。"""
        stage = GraphExtractionStage()
        ctx = self._make_ctx()
        ctx.result.errors = []
        ctx.result.graphs = None

        stage.run(ctx)
        # 无 graph 模块时静默跳过，不抛异常

    def test_blueprint_metadata_stage_runs(self):
        """BlueprintMetadataStage 正常运行（无 blueprint 时静默跳过）。"""
        stage = BlueprintMetadataStage()
        ctx = self._make_ctx()
        ctx.result.errors = []
        # 移除 blueprint 属性以触发静默跳过
        ctx.result.blueprint = None

        stage.run(ctx)
        # 应该能正常运行（即使返回 None）

    def test_kismet_decompile_stage_runs(self):
        """KismetDecompileStage 正常运行（无 kismet 模块时静默跳过）。"""
        stage = KismetDecompileStage()
        ctx = self._make_ctx()
        ctx.result.errors = []
        ctx.result.decompiled_functions = None

        stage.run(ctx)
        # 无 kismet 模块时静默跳过，不抛异常

    def test_component_extraction_stage_runs(self):
        """ComponentExtractionStage 正常运行（无组件模块时静默跳过）。"""
        stage = ComponentExtractionStage()
        ctx = self._make_ctx()
        ctx.result.errors = []
        ctx.result.components = None

        stage.run(ctx)
        # 无 component_extractor 模块时静默跳过，不抛异常

    def test_dependency_analysis_stage_runs(self):
        """DependencyAnalysisStage 正常运行。"""
        stage = DependencyAnalysisStage()
        ctx = self._make_ctx()
        ctx.result.errors = []
        ctx.result.imports = None
        ctx.result.soft_references = None
        ctx.result.circular_deps = None
        # Mock summary 为正确的类型
        from uasset_read.serializers.package_summary import PackageFileSummary
        ctx.summary = PackageFileSummary(
            tag=0x9E2A83C1,
            legacy_file_version=-7,
            name_count=1,
            name_offset=64,
            soft_object_paths_count=0,
            soft_object_paths_offset=0,
        )

        stage.run(ctx)
        # 应该能正常运行（没有 SoftObjectPaths 数据时）

    def test_parent_asset_stage_skips_without_flag(self):
        """ParentAssetStage 在未启用时跳过。"""
        stage = ParentAssetStage()
        ctx = self._make_ctx()
        ctx.include_parent_assets = False
        ctx.result.errors = []

        stage.run(ctx)
        # 未启用时静默跳过

    def test_parent_asset_stage_runs_with_flag(self):
        """ParentAssetStage 在启用时尝试运行。"""
        stage = ParentAssetStage()
        ctx = self._make_ctx()
        ctx.include_parent_assets = True
        ctx.result.errors = []

        stage.run(ctx)
        # 应该尝试解析（可能无父资产但应不报错）
