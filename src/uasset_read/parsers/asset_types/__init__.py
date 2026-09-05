"""Asset type parser module — Dedicated parsers for specific UE asset types.

All handlers return opaque partial metadata (raw byte samples),
not attempting to parse the UE standard Serialize layout.

Handlers are bootstrapped deterministically by ``get_class_registry()``
on first access — no module-level side effects required.

All handlers directly implement the ``ClassHandler`` protocol.
"""

from __future__ import annotations

import inspect
import logging
import struct
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport

from uasset_read.parsers.class_registry import (
    ClassHandler,
    HandlerResult,
    get_class_registry,
)
from uasset_read.parsers.asset_types.property_metadata import build_property_metadata

logger = logging.getLogger(__name__)

# Opaque stub factory (replaces 40 deleted stub files)
from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

# Dedicated asset-type parsers. Imported statically: the registration table below
# names them directly, so a missing parser is an ImportError at import time rather
# than a silently skipped handler.
from uasset_read.parsers.asset_types.anim_blueprint import AnimBlueprintHandler
from uasset_read.parsers.asset_types.anim_montage import AnimMontageHandler
from uasset_read.parsers.asset_types.anim_sequence import AnimSequenceHandler
from uasset_read.parsers.asset_types.curve_table import parse_curve_table
from uasset_read.parsers.asset_types.data_table import parse_data_table
from uasset_read.parsers.asset_types.level_sequence import parse_level_sequence
from uasset_read.parsers.asset_types.movie_scene import MovieSceneHandler
from uasset_read.parsers.asset_types.movie_scene_control_rig import (
    MovieSceneControlRigParameterSectionHandler,
    MovieSceneControlRigParameterTrackHandler,
)
from uasset_read.parsers.asset_types.niagara_node import NiagaraNodeHandler
from uasset_read.parsers.asset_types.niagara_projection import NIAGARA_HANDLERS
from uasset_read.parsers.asset_types.skeleton import parse_skeleton
from uasset_read.parsers.asset_types.sound_wave import parse_sound_wave
from uasset_read.parsers.asset_types.user_defined import parse_user_defined

__all__ = [
    "parse_material_instance",
    "register_asset_type_handlers",
    "NiagaraNodeHandler",
    "PropertyMetadataHandler",
]


def parse_material_instance(
    archive: "FArchive", name_map: list, export: "ObjectExport"
) -> dict:
    """Parse MaterialInstanceConstant export — delegates to IR builder pipeline."""
    return {"asset_type": "MaterialInstance", "material_type": "MaterialInstance"}


class AssetTypeHandler(ClassHandler):
    """Wrap parse_*() functions as ClassHandler."""

    def __init__(
        self,
        class_names: List[str],
        parse_func: Callable[..., Dict[str, Any]],
        handler_name: str,
    ) -> None:
        self._class_names = set(class_names)
        self._parse_func = parse_func
        self._handler_name = handler_name
        # 向后兼容：如果 parse_func 接受第三个参数（export），则传递。
        # Resolved once at construction; parse() is on the per-export hot path.
        self._takes_export = len(inspect.signature(parse_func).parameters) >= 3

    def can_handle(self, class_name: str) -> bool:
        return class_name in self._class_names

    @property
    def handler_name(self) -> str:
        return self._handler_name

    def parse(
        self,
        export: "ObjectExport",
        archive: "FArchive",
        context: Optional[Any] = None,
    ) -> HandlerResult:
        try:
            name_map = context if isinstance(context, list) else []
            if self._takes_export:
                data = self._parse_func(archive, name_map, export)
            else:
                data = self._parse_func(archive, name_map)
            return HandlerResult(
                success=True,
                data=data,
            )
        except (KeyError, TypeError, ValueError, struct.error) as e:
            logger.warning(
                "AssetTypeHandler '%s' failed for '%s': %s",
                self._handler_name,
                export.object_name,
                e,
            )
            return HandlerResult(
                success=False,
                error_message=str(e),
            )


class PropertyMetadataHandler(ClassHandler):
    """Project tagged properties while leaving native serialization opaque."""

    def __init__(self, class_name: str) -> None:
        self._class_name = class_name

    def can_handle(self, class_name: str) -> bool:
        return class_name == self._class_name

    @property
    def handler_name(self) -> str:
        return f"{self._class_name}PropertyMetadataHandler"

    def parse(
        self,
        export: "ObjectExport",
        archive: "FArchive",
        context: Optional[Any] = None,
    ) -> HandlerResult:
        tail_offset = archive.tell()
        serial_end = export.serial_offset + export.serial_size
        data = build_property_metadata(
            self._class_name,
            list(getattr(export, "properties", None) or []),
            tail_offset=tail_offset,
            tail_size=max(0, serial_end - tail_offset),
        )
        return HandlerResult(
            success=True,
            data=data,
        )


# Class names -> dedicated parser, in registration order (the registry resolves the
# first match, so this order is the dispatch priority). A `None` parser means the
# generic opaque partial-metadata stub: 43 of these 55 classes have no custom
# Serialize layout implemented yet and are reported as `partial_metadata`.
_ASSET_TYPE_HANDLERS: tuple[tuple[tuple[str, ...], Callable[..., Any] | type[ClassHandler] | None, str], ...] = (
    (("AnimSequence",), AnimSequenceHandler, "AnimSequenceHandler"),
    (("AnimBlueprintGeneratedClass",), AnimBlueprintHandler, "AnimBlueprintHandler"),
    (("AnimMontage",), AnimMontageHandler, "AnimMontageHandler"),
    (("SoundWave",), parse_sound_wave, "SoundWaveHandler"),
    (("SoundAttenuation",), None, "SoundAttenuationHandler"),
    (("AnimationDataModel",), None, "AnimDataModelHandler"),
    (("DataTable",), parse_data_table, "DataTableHandler"),
    (("CurveTable",), parse_curve_table, "CurveTableHandler"),
    (("Skeleton",), parse_skeleton, "SkeletonHandler"),
    (("StringTable",), None, "StringTableHandler"),
    (("PoseAsset",), None, "PoseAssetHandler"),
    (("AnimBoneCompressionSettings",), None, "AnimBoneCompressionHandler"),
    (("AnimCurveCompressionCodec",), None, "AnimCurveCompressionHandler"),
    (("SubsurfaceProfile",), None, "SubsurfaceProfileHandler"),
    (("FoliageType",), None, "FoliageTypeHandler"),
    (("SkeletalMeshLODSettings",), None, "SkeletalMeshLODSettingsHandler"),
    (("MovieScene",), MovieSceneHandler, "MovieSceneHandler"),
    (
        ("MovieSceneControlRigParameterTrack",),
        MovieSceneControlRigParameterTrackHandler,
        "MovieSceneControlRigParameterTrackHandler",
    ),
    (
        ("MovieSceneControlRigParameterSection",),
        MovieSceneControlRigParameterSectionHandler,
        "MovieSceneControlRigParameterSectionHandler",
    ),
    (("CurveFloat",), None, "CurveFloatHandler"),
    (("AnimComposite",), None, "AnimCompositeHandler"),
    (
        ("AnimBlendSpace", "AnimBlendSpace1D", "AimOffsetBlendSpace", "AimOffsetBlendSpace1D"),
        None,
        "AnimBlendSpaceHandler",
    ),
    (("SoundConcurrency",), None, "SoundConcurrencyHandler"),
    (("DialogueWave",), None, "DialogueWaveHandler"),
    (("DialogueVoice",), None, "DialogueVoiceHandler"),
    (("CurveLinearColor",), None, "CurveLinearColorHandler"),
    (("CurveVector",), None, "CurveVectorHandler"),
    (("TextureRenderTarget2D", "TextureRenderTargetCube"), None, "TextureRenderTargetHandler"),
    (("PhysicsAsset",), None, "PhysicsAssetHandler"),
    (("PhysicalMaterial",), None, "PhysicalMaterialHandler"),
    (("AnimLayerInterface",), None, "AnimLayerInterfaceHandler"),
    (("SoundMix",), None, "SoundMixHandler"),
    (("SoundClass",), None, "SoundClassHandler"),
    (("SoundSubmix",), None, "SoundSubmixHandler"),
    (("BehaviorTree",), None, "BehaviorTreeHandler"),
    (("BlackboardData",), None, "BlackboardDataHandler"),
    (("DataAsset",), None, "DataAssetHandler"),
    (("PrimaryDataAsset",), None, "PrimaryDataAssetHandler"),
    (("Landscape",), None, "LandscapeHandler"),
    (("LandscapeGrassType",), None, "LandscapeGrassTypeHandler"),
    (("LandscapeLayerInfoObject",), None, "LandscapeLayerInfoHandler"),
    (("World",), None, "WorldHandler"),
    (("Level",), None, "LevelHandler"),
    (("ParticleSystem",), None, "ParticleSystemHandler"),
    (("WidgetBlueprintGeneratedClass", "WidgetBlueprint"), None, "WidgetBlueprintHandler"),
    (("Texture2DArray",), None, "Texture2DArrayHandler"),
    (("VolumeTexture",), None, "VolumeTextureHandler"),
    (("MediaPlayer",), None, "MediaPlayerHandler"),
    (("MediaTexture",), None, "MediaTextureHandler"),
    (("MediaSource",), None, "MediaSourceHandler"),
    (("ClothAsset",), None, "ClothAssetHandler"),
    (("GroomAsset",), None, "GroomAssetHandler"),
    (("SparseVolumeTexture",), None, "SparseVolumeTextureHandler"),
    (("LevelSequence",), parse_level_sequence, "LevelSequenceHandler"),
    (
        ("UserDefinedEnum", "UserDefinedStruct"),
        parse_user_defined,
        "UserDefinedHandler",
    ),
)


def register_asset_type_handlers() -> None:
    """Register asset type parsers to ClassHandlerRegistry."""
    registry = get_class_registry()

    handlers: List[ClassHandler] = [
        PropertyMetadataHandler("CubeBuilder"),
        PropertyMetadataHandler("StaticMesh"),
        PropertyMetadataHandler("SkeletalMesh"),
        PropertyMetadataHandler("Material"),
        AssetTypeHandler(
            class_names=["MaterialInstance", "MaterialInstanceConstant"],
            parse_func=parse_material_instance,
            handler_name="MaterialInstanceHandler",
        ),
        PropertyMetadataHandler("Texture2D"),
        PropertyMetadataHandler("TextureCube"),
        PropertyMetadataHandler("SoundCue"),
        PropertyMetadataHandler("MaterialFunction"),
        PropertyMetadataHandler("MaterialParameterCollection"),
        PropertyMetadataHandler("ReverbEffect"),
        # #521: Niagara handlers
        *NIAGARA_HANDLERS,
        NiagaraNodeHandler(),
    ]

    for class_names, parse_func, handler_name in _ASSET_TYPE_HANDLERS:
        if parse_func is None:
            handlers.append(
                AssetTypeHandler(
                    class_names=list(class_names),
                    parse_func=make_opaque_stub(),
                    handler_name=handler_name,
                ),
            )
        elif isinstance(parse_func, type) and issubclass(parse_func, ClassHandler):
            handlers.append(parse_func())
        else:
            handlers.append(
                AssetTypeHandler(
                    class_names=list(class_names),
                    parse_func=parse_func,
                    handler_name=handler_name,
                ),
            )

    for handler in handlers:
        registry.register(handler)
        logger.debug("Registered asset type handler: %s", handler.handler_name)
