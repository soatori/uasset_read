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
from typing import TYPE_CHECKING, Any, Callable
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

# Opaque partial-metadata handler (replaces 40 deleted stub files)
from uasset_read.parsers.asset_types.opaque_stub import parse_opaque_stub

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


def parse_material_instance(archive: "FArchive", name_map: list, export: "ObjectExport") -> dict:
    """Parse MaterialInstanceConstant export — metadata placeholder only, no decode."""
    return {"asset_type": "MaterialInstance", "material_type": "MaterialInstance"}


class AssetTypeHandler(ClassHandler):
    """Wrap parse_*() functions as ClassHandler."""

    def __init__(
        self,
        class_names: list[str],
        parse_func: Callable[..., dict[str, Any]],
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
        context: Any | None = None,
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
        context: Any | None = None,
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


# Opaque class names that use parse_opaque_stub — no custom Serialize layout yet.
_OPAQUE_STUB_CLASS_NAMES: frozenset[str] = frozenset({
    "SoundAttenuation",
    "AnimationDataModel",
    "StringTable",
    "PoseAsset",
    "AnimBoneCompressionSettings",
    "AnimCurveCompressionCodec",
    "SubsurfaceProfile",
    "FoliageType",
    "SkeletalMeshLODSettings",
    "CurveFloat",
    "AnimComposite",
    "AnimBlendSpace",
    "AnimBlendSpace1D",
    "AimOffsetBlendSpace",
    "AimOffsetBlendSpace1D",
    "SoundConcurrency",
    "DialogueWave",
    "DialogueVoice",
    "CurveLinearColor",
    "CurveVector",
    "TextureRenderTarget2D",
    "TextureRenderTargetCube",
    "PhysicsAsset",
    "PhysicalMaterial",
    "AnimLayerInterface",
    "SoundMix",
    "SoundClass",
    "SoundSubmix",
    "BehaviorTree",
    "BlackboardData",
    "DataAsset",
    "PrimaryDataAsset",
    "Landscape",
    "LandscapeGrassType",
    "LandscapeLayerInfoObject",
    "World",
    "Level",
    "ParticleSystem",
    "WidgetBlueprintGeneratedClass",
    "WidgetBlueprint",
    "Texture2DArray",
    "VolumeTexture",
    "MediaPlayer",
    "MediaTexture",
    "MediaSource",
    "ClothAsset",
    "GroomAsset",
    "SparseVolumeTexture",
})

# Dedicated parsers only (opaque stubs are registered from _OPAQUE_STUB_CLASS_NAMES).
_ASSET_TYPE_HANDLERS: tuple[tuple[tuple[str, ...], Callable[..., Any] | type[ClassHandler], str], ...] = (
    (("AnimSequence",), AnimSequenceHandler, "AnimSequenceHandler"),
    (("AnimBlueprintGeneratedClass",), AnimBlueprintHandler, "AnimBlueprintHandler"),
    (("AnimMontage",), AnimMontageHandler, "AnimMontageHandler"),
    (("SoundWave",), parse_sound_wave, "SoundWaveHandler"),
    (("DataTable",), parse_data_table, "DataTableHandler"),
    (("CurveTable",), parse_curve_table, "CurveTableHandler"),
    (("Skeleton",), parse_skeleton, "SkeletonHandler"),
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

    handlers: list[ClassHandler] = [
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

    for class_name in sorted(_OPAQUE_STUB_CLASS_NAMES):
        handlers.append(
            AssetTypeHandler(
                class_names=[class_name],
                parse_func=parse_opaque_stub,
                handler_name=f"{class_name}Handler",
            ),
        )

    for class_names, parse_func, handler_name in _ASSET_TYPE_HANDLERS:
        if isinstance(parse_func, type) and issubclass(parse_func, ClassHandler):
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
