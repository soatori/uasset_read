"""class-specific payload 类型识别 + tolerant skip 辅助函数。

当通用 property parser 进入不支持的专用序列化区域时，
此模块提供类型识别和安全跳过逻辑。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

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
    # P0: Animation
    "AnimationDataModel",
    # P1: Niagara
    "NiagaraMeshRendererProperties",
    "NiagaraNodeParameterMapGet",
    "NiagaraNode",
    "NiagaraSystem",
    # P1: MovieScene
    "MovieScene",
    "MovieSceneSceneCaptureParams",
    # P2: MetaSound
    "MetasoundEditorGraph",
    "MetasoundEditorGraphInputObjectArray",
    "MetasoundEditorGraphMemberDefaultObjectArray",
    # P2: K2Node
    "K2Node_FunctionEntry",
    "K2Node_FormatText",
    # P2: Material
    "MaterialExpressionDynamicParameter",
    "MaterialExpression",
    # P3: 其他
    "SkySphereMesh",
    "InheritableComponentHandler",
    "AggGeom_",
)


def should_skip_export_for_tolerant_parsing(export: "ObjectExport") -> bool:
    """判断是否应对某 export 使用 tolerant skip（不尝试解析属性）。

    Args:
        export: ObjectExport 实例

    Returns:
        True 表示应跳过属性解析，仅保留 export 元数据
    """
    object_name = str(export.object_name)
    return object_name.startswith(SKIP_CLASS_PREFIXES)


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
        payload_end = export.serial_offset + export.script_serial_offset + export.script_serial_size
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
