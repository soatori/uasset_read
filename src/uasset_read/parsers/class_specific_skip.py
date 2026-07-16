from __future__ import annotations

"""class-specific payload 类型识别 + tolerant skip 辅助函数。

当通用 property parser 进入不支持的专用序列化区域时，
此模块提供类型识别和安全跳过逻辑。
"""

import logging
from typing import TYPE_CHECKING, Optional

from uasset_read.parsers.class_registry import (
    FallbackPolicy,
    get_class_registry,
)

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary

logger = logging.getLogger(__name__)

# 需要跳过的 export class 名称前缀/关键字
# 这些 class 的序列化数据不完全兼容通用 property parser
SKIP_CLASS_PREFIXES = (
    # P0: Builder / Brush
    "CubeBuilder",
    "GeomModifier_",
    "BrushBuilder",
    # P0: Animation — 已移至 opaque 白名单（#166）
    # "AnimationDataModel",
    # P1: Niagara
    "NiagaraMeshRendererProperties",
    "NiagaraNodeParameterMapGet",
    "NiagaraNode",
    "NiagaraSystem",
    # P1: MovieScene — 已移至 opaque 白名单（#164）
    # "MovieScene",
    # "MovieSceneSceneCaptureParams",
    # P2: MetaSound — 已移至 opaque 白名单（#165）
    # "MetasoundEditorGraph",
    # "MetasoundEditorGraphInputObjectArray",
    # "MetasoundEditorGraphMemberDefaultObjectArray",
    # P2: K2Node
    # K2Node_FunctionEntry 已从 skip 列表移除（#286）：
    # 通用 tagged property parser 可处理，K2Node_FunctionEntry 的特有字段
    # 通过 PropertyTag 序列化，不需要跳过。跳过会导致合法资产被标记 partial。
    # "K2Node_FunctionEntry",
    "K2Node_FormatText",
    # P2: Material
    # MaterialExpressionDynamicParameter 已从 skip 列表移除（#136 延伸）：
    # 通用 tagged property parser 可处理，失败时由 generic fallback 兜底。
    # MaterialExpression 已从 skip 列表移除（#136）：
    # 通用 tagged property parser 可处理大部分 MaterialExpression 子类。
    # 解析失败的子类由 generic fallback（opaque/partial）兜底。
    # "MaterialExpression",
    # P3: 其他
    "SkySphereMesh",
    "InheritableComponentHandler",
    "AggGeom_",
)

# 需要跳过的精确 class 名称（不使用前缀匹配）
# 这些 class 使用完全自定义的序列化格式，无法用通用 parser 处理
#
# 注意：已迁移到 class_serialization_strategy.py _SKIP_CLASSES 的类不再列出，
# 包括：NiagaraGraph, NiagaraScript, NiagaraDataInterface 及其子类、
# NiagaraSystem（保留在 _OPAQUE_CLASSES）、AnimBlueprintExtension、
# AnimComposite、AnimPoseSnapshot、ImpulseResponse、SoundConcurrency、
# SoundMix、SoundClass、ReverbEffect、AmbientSound。
# 完整 skip 策略以 CLASS_STRATEGY_TABLE 为唯一权威来源。
SKIP_CLASS_NAMES = {
    # Niagara — Renderer / Emitter（前缀匹配由 SKIP_CLASS_PREFIXES 处理）
    "NiagaraEmitter",
    "NiagaraSpriteRendererProperties",
    "NiagaraMeshRendererProperties",
    "NiagaraRibbonRendererProperties",
    "NiagaraRendererProperties",
    "NiagaraEmitterProperties",
}


def should_skip_export_for_tolerant_parsing(
    export: "ObjectExport",
    class_name: Optional[str] = None,
) -> bool:
    """判断是否应对某 export 使用 tolerant skip（不尝试解析属性）。

    检查顺序：
    1. class handler registry 中是否有 handler 且其 fallback_policy == SKIP
    2. export.object_name 是否以 SKIP_CLASS_PREFIXES 开头
    3. class_name 是否在 SKIP_CLASS_NAMES 中（精确匹配）
    4. class_name 是否以 SKIP_CLASS_PREFIXES 开头

    Args:
        export: ObjectExport 实例
        class_name: 可选的类名（从 class_index 解析）

    Returns:
        True 表示应跳过属性解析，仅保留 export 元数据
    """
    # 检查 1: registry handler fallback policy
    if class_name is not None:
        registry = get_class_registry()
        handler = registry.find_handler(class_name)
        if handler is not None and handler.fallback_policy == FallbackPolicy.SKIP:
            return True

    # 检查 2-4: 原有 skip list（作为 fallback policy）
    object_name = str(export.object_name)
    if object_name.startswith(SKIP_CLASS_PREFIXES):
        return True
    if class_name is not None and class_name in SKIP_CLASS_NAMES:
        return True
    if class_name is not None and class_name.startswith(SKIP_CLASS_PREFIXES):
        return True
    return False


def skip_export_payload(
    archive: "FArchive",
    export: "ObjectExport",
    summary: "PackageFileSummary",
) -> None:
    """安全跳过单个 export 的 payload 数据。

    Seek 过该 export 的属性区域，不尝试解析。

    Args:
        archive: FArchive 实例
        export: ObjectExport 实例
        summary: PackageFileSummary 实例
    """
    from uasset_read.constants import UE5_SCRIPT_SERIALIZATION_OFFSET

    if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
        payload_end = export.serial_offset + export.script_serialization_end_offset
    else:
        payload_end = export.serial_offset + export.serial_size

    # 确保不超过文件大小
    file_size = archive.total_size()
    safe_end = min(payload_end, file_size)

    logger.debug(
        "Skipping export '%s' payload: seek from %d to %d (%d bytes)",
        export.object_name,
        archive.tell(),
        safe_end,
        safe_end - archive.tell(),
    )
    archive.seek(safe_end)
