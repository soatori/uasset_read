"""资产类型解析器模块 — 特定 UE 资产类型的专用解析器。

所有 handler 返回 opaque partial metadata（原始字节样本），
不尝试解析 UE 标准 Serialize 布局。
在模块加载时自动注册为 ClassHandler，集成到主解析管线。
"""
from __future__ import annotations

import logging
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
    """将 Handler 类（如 AnimBlueprintHandler）适配为 ClassHandler 接口。

    Handler 类的 handle(export, context) 方法与 ClassHandler.parse(export, archive, context)
    接口不匹配，此类负责桥接两者。
    """

    def __init__(self, handler_instance: Any, handler_name: str) -> None:
        self._handler = handler_instance
        self._handler_name = handler_name
        # 从 Handler 类名推断支持的 class names
        # 例如 AnimBlueprintHandler -> AnimBlueprintGeneratedClass
        self._class_names = self._infer_class_names(handler_instance)

    def _infer_class_names(self, handler_instance: Any) -> set[str]:
        """从 Handler 实例推断支持的 class names。"""
        # 映射表：Handler 类名 -> 支持的 UE class names
        handler_class_map = {
            "AnimBlueprintHandler": {"AnimBlueprintGeneratedClass"},
            "AnimSequenceHandler": {"AnimSequence"},
            "AnimMontageHandler": {"AnimMontage"},
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
        """调用 Handler.handle(export, context) 并转换为 HandlerResult。"""
        try:
            status = self._handler.handle(export, context)
            # 将 ParseStatus 转换为 HandlerResult
            success = status.value in ("success", "partial")

            # 从 export.custom_data 提取实际数据
            # Handler 会将数据存储在 export.custom_data 中
            custom_data = getattr(export, "custom_data", {})
            data = {}
            if custom_data:
                # 根据 handler 类型提取对应的数据
                for key in ["anim_blueprint", "anim_sequence", "anim_montage"]:
                    if key in custom_data:
                        data[key] = custom_data[key]

            # 添加 parse_status
            data["parse_status"] = status.value

            return HandlerResult(
                success=success,
                data=data,
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )
        except Exception as e:
            logger.debug(
                "HandlerClassAdapter '%s' failed for '%s': %s",
                self._handler_name, export.object_name, e,
            )
            return HandlerResult(
                success=False,
                error_message=str(e),
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )


# 导入专用解析函数
from uasset_read.parsers.asset_types.static_mesh import parse_static_mesh
from uasset_read.parsers.asset_types.skeletal_mesh import parse_skeletal_mesh
from uasset_read.parsers.asset_types.material import parse_material
from uasset_read.parsers.asset_types.material_instance import parse_material_instance
from uasset_read.parsers.asset_types.texture2d import parse_texture2d
__all__ = [
    "parse_static_mesh",
    "parse_skeletal_mesh",
    "parse_material",
    "parse_material_instance",
    "parse_texture2d",
    "parse_texture_cube",
    "parse_anim_sequence",
    "parse_sound_wave",
    "parse_sound_cue",
    "register_asset_type_handlers",
    "AnimSequenceHandler",
    "HandlerClassAdapter",
]


class AssetTypeHandler(ClassHandler):
    """将 parse_*() 函数包装为 ClassHandler。"""

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
        except Exception as e:
            logger.debug(
                "AssetTypeHandler '%s' failed for '%s': %s",
                self._handler_name, export.object_name, e,
            )
            return HandlerResult(
                success=False,
                error_message=str(e),
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )


def register_asset_type_handlers() -> None:
    """将资产类型解析器注册到 ClassHandlerRegistry。"""
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

    # 可选解析器（导入成功则注册）
    _optional = [
        ("texture_cube", "parse_texture_cube", ["TextureCube"], "TextureCubeHandler"),
        ("anim_sequence", "AnimSequenceHandler", ["AnimSequence"], "AnimSequenceHandler"),
        ("anim_blueprint", "AnimBlueprintHandler", ["AnimBlueprintGeneratedClass"], "AnimBlueprintHandler"),
        ("anim_montage", "AnimMontageHandler", ["AnimMontage"], "AnimMontageHandler"),
        ("sound_wave", "parse_sound_wave", ["SoundWave"], "SoundWaveHandler"),
        ("sound_attenuation", "parse_sound_attenuation", ["SoundAttenuation"], "SoundAttenuationHandler"),
        ("sound_cue", "parse_sound_cue", ["SoundCue"], "SoundCueHandler"),
        ("anim_data_model", "parse_anim_data_model", ["AnimationDataModel"], "AnimDataModelHandler"),
        ("data_table", "parse_data_table", ["DataTable"], "DataTableHandler"),
        ("curve_table", "parse_curve_table", ["CurveTable"], "CurveTableHandler"),
        ("skeleton", "parse_skeleton", ["Skeleton"], "SkeletonHandler"),
        ("level_sequence", "parse_level_sequence", ["LevelSequence"], "LevelSequenceHandler"),
        ("string_table", "parse_string_table", ["StringTable"], "StringTableHandler"),
        ("pose_asset", "parse_pose_asset", ["PoseAsset"], "PoseAssetHandler"),
        ("anim_bone_compression", "parse_anim_bone_compression_settings", ["AnimBoneCompressionSettings"], "AnimBoneCompressionHandler"),
        ("anim_curve_compression", "parse_anim_curve_compression_codec", ["AnimCurveCompressionCodec"], "AnimCurveCompressionHandler"),
        ("subsurface_profile", "parse_subsurface_profile", ["SubsurfaceProfile"], "SubsurfaceProfileHandler"),
        ("foliage_type", "parse_foliage_type", ["FoliageType"], "FoliageTypeHandler"),
        ("skeletal_mesh_lod_settings", "parse_skeletal_mesh_lod_settings", ["SkeletalMeshLODSettings"], "SkeletalMeshLODSettingsHandler"),
    ]
    for module, func_name, class_names, handler_name in _optional:
        try:
            mod = __import__(
                f"uasset_read.parsers.asset_types.{module}",
                fromlist=[func_name],
            )
            parse_func = getattr(mod, func_name)
            # 检查是否是类（如 AnimBlueprintHandler）
            if isinstance(parse_func, type):
                # 类需要实例化，创建适配器包装
                handler_instance = parse_func()
                # 创建适配器：将 ClassHandler.parse(export, archive, context)
                # 转换为 Handler.handle(export, context)
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
        except ImportError:
            pass

    for handler in handlers:
        registry.register(handler)
        logger.debug("Registered asset type handler: %s", handler.handler_name)


# 模块加载时自动注册
register_asset_type_handlers()
