"""后处理管线 — 将 _post_process 拆分为独立的 stage。

每个 stage 负责一个特定的后处理步骤，通过 PostProcessPipeline 顺序执行。
单个 stage 失败不影响其他 stage 的执行。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING, Any, Optional, List, Union, Sequence, Protocol, runtime_checkable,
)

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.link.linker import PackageLinker
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectImport, ObjectExport
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)


@dataclass
class PostProcessContext:
    """后处理上下文 — 在各 stage 之间传递共享数据。"""
    path: str
    archive: "FArchive"
    summary: "PackageFileSummary"
    name_map: List[str]
    import_map: List["ObjectImport"]
    export_map: List["ObjectExport"]
    result: Union["ParseResult", "LinkerParseResult"]
    tolerant: bool = True
    linker: Optional["PackageLinker"] = None
    include_parent_assets: bool = False
    asset_roots: Optional[Sequence[str]] = None
    archive_factory: Optional[Any] = None
    # stage 间共享的中间数据
    graphs_list: Optional[List] = None
    blueprint_metadata: Optional[Any] = None


@runtime_checkable
class PostProcessStage(Protocol):
    """Stage 协议 — 每个后处理 stage 实现此接口。"""

    def run(self, ctx: PostProcessContext) -> None:
        """执行后处理步骤，原地修改 ctx.result。"""
        ...


class PostProcessPipeline:
    """后处理管线 — 顺序执行 stage，单个 stage 失败不阻塞后续 stage。"""

    def __init__(self, stages: Optional[List[PostProcessStage]] = None) -> None:
        self.stages = stages or []

    def add_stage(self, stage: PostProcessStage) -> None:
        self.stages.append(stage)

    def execute(self, ctx: PostProcessContext) -> None:
        """按顺序执行所有 stage。"""
        for stage in self.stages:
            try:
                stage.run(ctx)
            except Exception as e:
                stage_name = type(stage).__name__
                logger.debug("后处理 stage '%s' 失败: %s", stage_name, e)
                if hasattr(ctx.result, 'warnings'):
                    ctx.result.warnings.append(f"{stage_name} error: {e}")


# ─── Stage 1: 图提取 ───────────────────────────────────────────────

class GraphExtractionStage:
    """提取蓝图图结构（UEdGraph 列表）。"""

    def run(self, ctx: PostProcessContext) -> None:
        try:
            from uasset_read.graph import extract_blueprint_graphs
        except ImportError:
            return  # graph 模块不存在时静默跳过

        if not hasattr(ctx.result, 'graphs'):
            return

        try:
            ctx.result.graphs = extract_blueprint_graphs(
                ctx.archive, ctx.summary, ctx.name_map,
                ctx.import_map, ctx.export_map,
                linker=ctx.linker,
            )
            ctx.graphs_list = ctx.result.graphs
        except ParseError as e:
            if hasattr(ctx.result, 'errors'):
                ctx.result.errors.append(f"graph extraction error: {e}")


# ─── Stage 2: 蓝图元数据提取 ──────────────────────────────────────

class BlueprintMetadataStage:
    """提取蓝图元数据（变量、函数签名、ParentClass 等）。"""

    def run(self, ctx: PostProcessContext) -> None:
        from uasset_read.serializers.object_resources import (
            detect_blueprint, find_main_blueprint_generated_class,
        )
        from uasset_read.blueprint import extract_blueprint_metadata

        if not hasattr(ctx.result, 'blueprint'):
            return

        asset_name = ctx.name_map[0] if ctx.name_map else None
        if not asset_name:
            return

        # 查找主 Blueprint export（包含 NewVariables）
        main_blueprint = None
        for export in ctx.export_map:
            is_bp = detect_blueprint(export, ctx.import_map, ctx.export_map) if ctx.import_map else False
            if is_bp and export.object_name:
                simple_asset_name = asset_name.split("/")[-1] if "/" in asset_name else asset_name
                if export.object_name == simple_asset_name:
                    main_blueprint = export
                    break

        blueprint_metadata = None

        # 尝试从 UBlueprint export 提取
        if main_blueprint:
            blueprint_metadata = self._extract_metadata(
                main_blueprint, ctx, ctx.graphs_list,
            )

        # BPGC 回退（不包含 NewVariables，仅用于获取 ParentClass 等元数据）
        if not blueprint_metadata:
            main_bpgc = find_main_blueprint_generated_class(
                ctx.export_map, ctx.import_map, asset_name,
            )
            if main_bpgc:
                blueprint_metadata = self._extract_metadata(
                    main_bpgc, ctx, ctx.graphs_list, bpgc_fallback=True,
                )

        ctx.result.blueprint = blueprint_metadata
        ctx.blueprint_metadata = blueprint_metadata

    def _extract_metadata(self, export, ctx, graphs_list, *, bpgc_fallback=False):
        from uasset_read.blueprint import extract_blueprint_metadata

        owned_archive = ctx.archive_factory is not None
        temp_archive = ctx.archive_factory() if ctx.archive_factory else ctx.archive
        temp_archive.set_byte_swapping(ctx.archive._byte_swapping)
        suffix = " (BPGC)" if bpgc_fallback else ""
        try:
            meta, warn = extract_blueprint_metadata(
                export, temp_archive, ctx.import_map,
                ctx.export_map, ctx.name_map, ctx.summary,
                linker=ctx.linker,
                graphs=graphs_list,
            )
            if meta:
                if hasattr(ctx.result, 'errors') and warn:
                    ctx.result.errors.append(f"blueprint parent warning: {warn}")
                return meta
        except ParseError as e:
            if hasattr(ctx.result, 'errors'):
                ctx.result.errors.append(f"blueprint extraction error{suffix}: {e}")
        finally:
            if owned_archive:
                temp_archive.close()
        return None


# ─── Stage 3: Kismet 反编译 ──────────────────────────────────────

class KismetDecompileStage:
    """Kismet 字节码反编译为结构化 AST。"""

    def run(self, ctx: PostProcessContext) -> None:
        try:
            from uasset_read.kismet.pipeline import decompile_single_function  # noqa: F401
        except ImportError:
            return  # kismet/pipeline.py 不存在时静默跳过

        if not hasattr(ctx.result, 'decompiled_functions'):
            return

        try:
            from uasset_read.parse_uasset import _extract_kismet_decompiled

            decompiled = _extract_kismet_decompiled(
                ctx.path, ctx.archive, ctx.summary, ctx.name_map,
                ctx.import_map, ctx.export_map, ctx.tolerant, linker=ctx.linker,
            )
            ctx.result.decompiled_functions = decompiled
            if decompiled and getattr(ctx.result, "graphs", None):
                from uasset_read.kismet.semantic import enrich_decompiled_functions
                enrich_decompiled_functions(decompiled, ctx.result.graphs)
            if ctx.blueprint_metadata and not decompiled and hasattr(ctx.result, 'warnings'):
                ctx.result.warnings.append(
                    "Kismet decompilation: no functions decompiled (may have no bytecode)"
                )
        except Exception as e:
            if hasattr(ctx.result, 'warnings'):
                ctx.result.warnings.append(f"Kismet decompilation error: {e}")


# ─── Stage 4: 父资产解析 ──────────────────────────────────────────

class ParentAssetStage:
    """解析父资产（继承链上的 Blueprint）。"""

    def run(self, ctx: PostProcessContext) -> None:
        if not ctx.include_parent_assets:
            return
        from uasset_read.parse_uasset import _resolve_parent_assets
        _resolve_parent_assets(ctx.path, ctx.result, ctx.tolerant, ctx.asset_roots)


# ─── Stage 5: 组件提取 ────────────────────────────────────────────

class ComponentExtractionStage:
    """提取组件和 SCS 树。"""

    def run(self, ctx: PostProcessContext) -> None:
        try:
            from uasset_read.blueprint.component_extractor import (
                extract_components, extract_scs_tree,
            )
        except ImportError:
            return  # component_extractor 模块不存在

        try:
            if hasattr(ctx.result, 'components'):
                ctx.result.components = extract_components(ctx.export_map, ctx.import_map)
            # SCS 组件树提取 (Issue #70)
            try:
                scs_tree = extract_scs_tree(
                    ctx.export_map, ctx.import_map,
                    archive=ctx.archive, summary=ctx.summary, name_map=ctx.name_map,
                )
                if scs_tree and hasattr(ctx.result, 'metadata'):
                    ctx.result.metadata["scs_tree"] = scs_tree
            except Exception as e:
                if hasattr(ctx.result, 'warnings'):
                    ctx.result.warnings.append(f"SCS tree extraction error: {e}")
        except Exception as e:
            if hasattr(ctx.result, 'errors'):
                ctx.result.errors.append(f"component extraction error: {e}")


# ─── Stage 6: 依赖分析 ────────────────────────────────────────────

class DependencyAnalysisStage:
    """依赖分析：imports、soft_references、circular_deps。"""

    def run(self, ctx: PostProcessContext) -> None:
        from uasset_read.serializers.object_resources import (
            build_imports_list, read_soft_object_paths, detect_circular_deps,
        )

        try:
            if hasattr(ctx.result, 'imports'):
                ctx.result.imports = build_imports_list(ctx.import_map)
            if hasattr(ctx.result, 'soft_references'):
                ctx.result.soft_references = read_soft_object_paths(
                    ctx.archive, ctx.summary, ctx.name_map,
                )
            if hasattr(ctx.result, 'circular_deps'):
                ctx.result.circular_deps = detect_circular_deps(ctx.import_map)
        except ParseError as e:
            if hasattr(ctx.result, 'errors'):
                ctx.result.errors.append(f"dependency analysis error: {e}")


# ─── Stage 7: 一致性检查 ──────────────────────────────────────────

class ConsistencyCheckStage:
    """一致性检查：验证 name_map 等关键数据完整性。"""

    def run(self, ctx: PostProcessContext) -> None:
        # name_map 一致性检查
        if hasattr(ctx.result, 'name_map') and not ctx.result.name_map:
            if ctx.summary is not None and getattr(ctx.summary, 'name_count', 0) > 0:
                if hasattr(ctx.result, 'errors'):
                    ctx.result.errors.append(
                        f"name_map 为空（summary.name_count={ctx.summary.name_count}），"
                        f"名称表读取失败"
                    )

        # 设置成功标志
        ctx.result.is_success = len(ctx.result.errors) == 0


def build_default_pipeline() -> PostProcessPipeline:
    """构建默认后处理管线（7 个 stage 按依赖顺序排列）。"""
    return PostProcessPipeline([
        GraphExtractionStage(),       # 1. 图提取（先于元数据，传递 graphs 参数）
        BlueprintMetadataStage(),     # 2. 蓝图元数据提取
        KismetDecompileStage(),       # 3. Kismet 反编译
        ParentAssetStage(),           # 4. 父资产解析
        ComponentExtractionStage(),   # 5. 组件和 SCS 树提取
        DependencyAnalysisStage(),    # 6. 依赖分析
        ConsistencyCheckStage(),      # 7. 一致性检查 + 设置成功标志
    ])
