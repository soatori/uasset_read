"""class-specific payload 类型识别 + tolerant skip 辅助函数。

当通用 property parser 进入不支持的专用序列化区域时，
此模块提供类型识别和安全跳过逻辑。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

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

# 需要跳过的精确 class 名称（不使用前缀匹配）
# 这些 class 使用完全自定义的序列化格式，无法用通用 parser 处理
SKIP_CLASS_NAMES = {
    # Niagara — 使用 FNiagaraVariable 等自定义序列化器
    "NiagaraSystem",
    "NiagaraGraph",
    "NiagaraEmitter",
    "NiagaraScript",
    "NiagaraScriptSource",
    "NiagaraDataInterface",
    "NiagaraDataInterfaceExport",
    "NiagaraDataInterfaceGrid2D",
    "NiagaraDataInterfaceGrid3D",
    "NiagaraDataInterfaceSkeletalMesh",
    "NiagaraDataInterfaceTexture",
    "NiagaraDataInterfaceComponentRenderer",
    "NiagaraDataInterfaceAudioSubmix",
    "NiagaraDataInterfaceCurlNoise",
    "NiagaraDataInterfaceRenderTarget2D",
    "NiagaraDataInterfaceSkeletalMeshSlice",
    "NiagaraDataInterfaceStaticMesh",
    "NiagaraDataInterfaceRwGrid2D",
    "NiagaraDataInterfaceRwGrid3D",
    "NiagaraDataInterfaceNeighborGrid3D",
    "NiagaraDataInterfaceLandscape",
    "NiagaraDataInterfaceOcclusion",
    "NiagaraDataInterfaceParticleRead",
    "NiagaraDataInterfaceDebugColor",
    "NiagaraDataInterfaceGpuReadback",
    "NiagaraDataInterfaceAudio",
    "NiagaraDataInterfaceMediaTexture",
    "NiagaraDataInterfaceVideo",
    "NiagaraDataInterfaceVirtualTexture",
    "NiagaraDataInterfaceSparseVolumeTexture",
    # Niagara — Renderer / Emitter
    "NiagaraSpriteRendererProperties",
    "NiagaraMeshRendererProperties",
    "NiagaraRibbonRendererProperties",
    "NiagaraRendererProperties",
    "NiagaraEmitterProperties",
    # Anim — 使用自定义序列化
    "AnimBlueprintGeneratedClass",
    "AnimBlueprintExtension",
    "AnimSequence",
    "AnimMontage",
    "AnimComposite",
    "AnimPoseSnapshot",
    # Audio — ImpulseResponse 等使用特殊格式
    "ImpulseResponse",
    "SoundWave",
    "SoundCue",
    "SoundAttenuation",
    "SoundConcurrency",
    "SoundMix",
    "SoundClass",
    "ReverbEffect",
    "AmbientSound",
}


def should_skip_export_for_tolerant_parsing(
    export: "ObjectExport",
    class_name: Optional[str] = None,
) -> bool:
    """判断是否应对某 export 使用 tolerant skip（不尝试解析属性）。

    检查逻辑（任一匹配即跳过）：
    1. export.object_name 是否以 SKIP_CLASS_PREFIXES 开头
    2. class_name 是否在 SKIP_CLASS_NAMES 中（精确匹配）
    3. class_name 是否以 SKIP_CLASS_PREFIXES 开头

    Args:
        export: ObjectExport 实例
        class_name: 可选的类名（从 class_index 解析）

    Returns:
        True 表示应跳过属性解析，仅保留 export 元数据
    """
    object_name = str(export.object_name)
    # 检查 1: export 名称前缀匹配
    if object_name.startswith(SKIP_CLASS_PREFIXES):
        return True
    # 检查 2: class name 精确匹配
    if class_name is not None and class_name in SKIP_CLASS_NAMES:
        return True
    # 检查 3: class name 前缀匹配
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
