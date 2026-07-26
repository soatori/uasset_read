"""Asset type parser module — Dedicated parsers for specific UE asset types.

All handlers return opaque partial metadata (raw byte samples),
not attempting to parse the UE standard Serialize layout.

Handlers are bootstrapped deterministically by ``get_class_registry()``
on first access — no module-level side effects required.

Supports two registration methods:
1. Manual registration: explicitly register via register_asset_type_handlers()
2. Reflection registration: auto-scan handler classes in asset_types/ via discover_handlers()
"""
from __future__ import annotations

import importlib
import inspect
import logging
import struct
from pathlib import Path
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

logger = logging.getLogger(__name__)


class HandlerClassAdapter(ClassHandler):
    """Adapt the Handler class (e.g. AnimBlueprintHandler) to the ClassHandler interface.

    Handler method (export, context) does not match ClassHandler.parse(export, archive, context)
    interface; this class bridges the two.
    """

    def __init__(self, handler_instance: Any, handler_name: str) -> None:
        self._handler = handler_instance
        self._handler_name = handler_name
        # Infer supported class names from Handler class name
        # e.g. AnimBlueprintHandler -> AnimBlueprintGeneratedClass
        self._class_names = self._infer_class_names(handler_instance)

    def _infer_class_names(self, handler_instance: Any) -> set[str]:
        """Infer supported class names from Handler instance."""
        # Mapping table: Handler class name -> supported UE class names
        handler_class_map = {
            "AnimBlueprintHandler": {"AnimBlueprintGeneratedClass"},
            "AnimSequenceHandler": {"AnimSequence"},
            "AnimMontageHandler": {"AnimMontage"},
            "MovieSceneHandler": {"MovieScene"},
            "MovieSceneControlRigParameterTrackHandler": {"MovieSceneControlRigParameterTrack"},
            "MovieSceneControlRigParameterSectionHandler": {"MovieSceneControlRigParameterSection"},
        }
        class_name = type(handler_instance).__name__
        return handler_class_map.get(class_name, set())

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
        """Call Handler.handle(export, context) and convert to HandlerResult."""
        try:
            status = self._handler.handle(export, context)
            # Convert ParseStatus to HandlerResult
            success = status.value in ("success", "partial")

            # Extract actual data from export.custom_data
            # Handler will store data in export.custom_data
            custom_data = getattr(export, "custom_data", {})
            data = {}
            if custom_data:
                # Extract corresponding data based on handler type
                for key in [
                    "anim_blueprint", "anim_sequence", "anim_montage",
                    "movie_scene", "movie_scene_control_rig_track",
                    "movie_scene_control_rig_section",
                ]:
                    if key in custom_data:
                        data[key] = custom_data[key]

            # Add parse_status
            data["parse_status"] = status.value

            return HandlerResult(
                success=success,
                data=data,
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )
        except (KeyError, TypeError, ValueError, struct.error) as e:
            logger.warning(
                "HandlerClassAdapter '%s' failed for '%s': %s",
                self._handler_name, export.object_name, e,
            )
            return HandlerResult(
                success=False,
                error_message=str(e),
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )


def discover_handlers() -> Dict[str, Any]:
    """Auto-discover handlers in the asset_types/ directory.

    Scans all non-private Python modules to find classes with export_type and
    priority attributes. These classes are automatically registered to the
    handler mapping.

    Returns:
        Dict[str, Any]: export_type -> handler_class mapping
    """
    handlers: Dict[str, Any] = {}
    asset_types_dir = Path(__file__).parent

    for py_file in asset_types_dir.glob("*.py"):
        if py_file.name.startswith("_") or py_file.name == "opaque_stub.py":
            continue

        module_name = py_file.stem
        try:
            module = importlib.import_module(f".{module_name}", package=__name__)

            for name, obj in inspect.getmembers(module, inspect.isclass):
                if hasattr(obj, "export_type") and hasattr(obj, "priority"):
                    export_type = obj.export_type
                    if export_type not in handlers:
                        handlers[export_type] = obj
                        logger.debug(
                            "Auto-discovered handler: %s -> %s (priority=%d)",
                            export_type, obj.__name__, obj.priority,
                        )

        except (ImportError, OSError, AttributeError, ValueError) as e:
            logger.warning("Failed to load handler from %s: %s", py_file.name, e)

    return handlers


# Manually registered handler mapping (higher priority than auto-discovery)
manually_registered_handlers: Dict[str, Any] = {}

# Module-level cache: discover_handlers() result, avoid scanning file system every call
_handler_cache: Optional[Dict[str, Any]] = None


def register_handler(export_type: str, handler: Any) -> None:
    """Register handler manually (higher priority than auto-discovery)."""
    manually_registered_handlers[export_type] = handler


def get_handler(export_type: str) -> Optional[Any]:
    """Get handler, manual registration takes priority over auto-discovery.

    Uses module-level cache to avoid repeated file system scanning.
    Cache invalidates automatically on module reload (_handler_cache resets to None).

    Args:
        export_type: UE export type name

    Returns:
        Handler class or None
    """
    # Manual registration priority
    if export_type in manually_registered_handlers:
        return manually_registered_handlers[export_type]

    # Auto-discovery fallback (with cache)
    global _handler_cache
    if _handler_cache is None:
        _handler_cache = discover_handlers()

    if export_type in _handler_cache:
        return _handler_cache[export_type]

    return None


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
    "HandlerClassAdapter",
    "discover_handlers",
    "get_handler",
    "register_handler",
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


def register_asset_type_handlers() -> None:
    """Register asset type parsers to ClassHandlerRegistry."""
    registry = get_class_registry()

    handlers = [
        AssetTypeHandler(
            class_names=["StaticMesh"],
            parse_func=parse_static_mesh,
            handler_name="StaticMeshHandler",
        ),
        AssetTypeHandler(
            class_names=["SkeletalMesh"],
            parse_func=parse_skeletal_mesh,
            handler_name="SkeletalMeshHandler",
        ),
        AssetTypeHandler(
            class_names=["Material"],
            parse_func=parse_material,
            handler_name="MaterialHandler",
        ),
        AssetTypeHandler(
            class_names=["MaterialInstance", "MaterialInstanceConstant"],
            parse_func=parse_material_instance,
            handler_name="MaterialInstanceHandler",
        ),
        AssetTypeHandler(
            class_names=["Texture2D"],
            parse_func=parse_texture2d,
            handler_name="Texture2DHandler",
        ),
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
        ("sound_cue", "parse_sound_cue", ["SoundCue"], "SoundCueHandler"),
    ]
    for module, func_name, class_names, handler_name in _optional:
        try:
            mod = __import__(
                f"uasset_read.parsers.asset_types.{module}",
                fromlist=[func_name],
            )
            parse_func = getattr(mod, func_name)
            # Check if it is a class (e.g. AnimBlueprintHandler)
            if isinstance(parse_func, type):
                # Class needs instantiation, create adapter wrapper
                handler_instance = parse_func()
                # Create adapter: convert ClassHandler.parse(export, archive, context)
                # to Handler.handle(export, context)
                adapter = HandlerClassAdapter(handler_instance, handler_name)
                handlers.append(adapter)
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
