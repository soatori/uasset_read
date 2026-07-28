"""Asset type parser module — Dedicated parsers for specific UE asset types.

All handlers return opaque partial metadata (raw byte samples),
not attempting to parse the UE standard Serialize layout.

Handlers are bootstrapped deterministically by ``get_class_registry()``
on first access — no module-level side effects required.

All handlers directly implement the ``ClassHandler`` protocol.
"""
from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport

from uasset_read.parsers.class_registry import (
    ClassHandler,
    FallbackPolicy,
    HandlerResult,
    get_class_registry,
)
from uasset_read.parsers.asset_types.property_metadata import build_property_metadata

logger = logging.getLogger(__name__)


# Import dedicated parse functions
from uasset_read.parsers.asset_types.static_mesh import parse_static_mesh
from uasset_read.parsers.asset_types.skeletal_mesh import parse_skeletal_mesh
from uasset_read.parsers.asset_types.material import parse_material
from uasset_read.parsers.asset_types.material_instance import parse_material_instance
from uasset_read.parsers.asset_types.texture2d import parse_texture2d

# Import handler classes (for reflection registration)
from uasset_read.parsers.asset_types.anim_blueprint import AnimBlueprintHandler
from uasset_read.parsers.asset_types.anim_sequence import AnimSequenceHandler
from uasset_read.parsers.asset_types.anim_montage import AnimMontageHandler

__all__ = [
    "parse_static_mesh",
    "parse_skeletal_mesh",
    "parse_material",
    "parse_material_instance",
    "parse_texture2d",
    "register_asset_type_handlers",
    "AnimBlueprintHandler",
    "AnimSequenceHandler",
    "AnimMontageHandler",
    "PropertyMetadataHandler",
]


class AssetTypeHandler(ClassHandler):
    """Wrap parse_*() functions as ClassHandler."""

    def __init__(
        self,
        class_names: List[str],
        parse_func: Callable[["FArchive", List[str]], Dict[str, Any]],
        handler_name: str,
    ) -> None:
        self._class_names = set(class_names)
        self._parse_func = parse_func
        self._handler_name = handler_name

    def can_handle(self, class_name: str) -> bool:
        return class_name in self._class_names

    @property
    def handler_name(self) -> str:
        return self._handler_name

    @property
    def fallback_policy(self) -> FallbackPolicy:
        return FallbackPolicy.GENERIC_UOBJECT

    def parse(
        self,
        export: "ObjectExport",
        archive: "FArchive",
        context: Optional[Any] = None,
    ) -> HandlerResult:
        try:
            name_map = context if isinstance(context, list) else []
            data = self._parse_func(archive, name_map)
            return HandlerResult(
                success=True,
                data=data,
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )
        except (KeyError, TypeError, ValueError, struct.error) as e:
            logger.warning(
                "AssetTypeHandler '%s' failed for '%s': %s",
                self._handler_name, export.object_name, e,
            )
            return HandlerResult(
                success=False,
                error_message=str(e),
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
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

    @property
    def fallback_policy(self) -> FallbackPolicy:
        return FallbackPolicy.GENERIC_UOBJECT

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
            fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
        )
def register_asset_type_handlers() -> None:
    """Register asset type parsers to ClassHandlerRegistry."""
    registry = get_class_registry()

    handlers = [
        PropertyMetadataHandler("StaticMesh"),
        PropertyMetadataHandler("SkeletalMesh"),
        PropertyMetadataHandler("Material"),
        AssetTypeHandler(
            class_names=["MaterialInstance", "MaterialInstanceConstant"],
            parse_func=parse_material_instance,
            handler_name="MaterialInstanceHandler",
        ),
        PropertyMetadataHandler("Texture2D"),
        PropertyMetadataHandler("SoundCue"),
    ]

    # Optional parsers (register if import succeeds)
    _optional = [
        ("texture_cube", "parse_texture_cube", ["TextureCube"], "TextureCubeHandler"),
        ("anim_sequence", "AnimSequenceHandler", ["AnimSequence"], "AnimSequenceHandler"),
        ("anim_blueprint", "AnimBlueprintHandler", ["AnimBlueprintGeneratedClass"], "AnimBlueprintHandler"),
        ("anim_montage", "AnimMontageHandler", ["AnimMontage"], "AnimMontageHandler"),
        ("sound_wave", "parse_sound_wave", ["SoundWave"], "SoundWaveHandler"),
        ("sound_attenuation", "parse_sound_attenuation", ["SoundAttenuation"], "SoundAttenuationHandler"),
        ("anim_data_model", "parse_anim_data_model", ["AnimationDataModel"], "AnimDataModelHandler"),
        ("data_table", "parse_data_table", ["DataTable"], "DataTableHandler"),
        ("curve_table", "parse_curve_table", ["CurveTable"], "CurveTableHandler"),
        ("skeleton", "parse_skeleton", ["Skeleton"], "SkeletonHandler"),
        ("string_table", "parse_string_table", ["StringTable"], "StringTableHandler"),
        ("pose_asset", "parse_pose_asset", ["PoseAsset"], "PoseAssetHandler"),
        ("anim_bone_compression", "parse_anim_bone_compression_settings", ["AnimBoneCompressionSettings"], "AnimBoneCompressionHandler"),
        ("anim_curve_compression", "parse_anim_curve_compression_codec", ["AnimCurveCompressionCodec"], "AnimCurveCompressionHandler"),
        ("subsurface_profile", "parse_subsurface_profile", ["SubsurfaceProfile"], "SubsurfaceProfileHandler"),
        ("foliage_type", "parse_foliage_type", ["FoliageType"], "FoliageTypeHandler"),
        ("skeletal_mesh_lod_settings", "parse_skeletal_mesh_lod_settings", ["SkeletalMeshLODSettings"], "SkeletalMeshLODSettingsHandler"),
        ("movie_scene", "MovieSceneHandler", ["MovieScene"], "MovieSceneHandler"),
        ("movie_scene_control_rig", "MovieSceneControlRigParameterTrackHandler", ["MovieSceneControlRigParameterTrack"], "MovieSceneControlRigParameterTrackHandler"),
        ("movie_scene_control_rig", "MovieSceneControlRigParameterSectionHandler", ["MovieSceneControlRigParameterSection"], "MovieSceneControlRigParameterSectionHandler"),
    ]
    for module, func_name, class_names, handler_name in _optional:
        try:
            mod = __import__(
                f"uasset_read.parsers.asset_types.{module}",
                fromlist=[func_name],
            )
            parse_func = getattr(mod, func_name)
            # Check if it is a class that implements ClassHandler directly
            if isinstance(parse_func, type) and issubclass(parse_func, ClassHandler):
                # Class directly implements ClassHandler protocol
                handler_instance = parse_func()
                handlers.append(handler_instance)
            else:
                handlers.append(
                    AssetTypeHandler(
                        class_names=class_names,
                        parse_func=parse_func,
                        handler_name=handler_name,
                    ),
                )
        except ImportError as e:
            logger.debug("Skip asset type handler %s: %s", handler_name, e)

    for handler in handlers:
        registry.register(handler)
        logger.debug("Registered asset type handler: %s", handler.handler_name)
