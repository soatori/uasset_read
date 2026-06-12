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
    "register_asset_type_handlers",
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
        ("anim_sequence", "parse_anim_sequence", ["AnimSequence"], "AnimSequenceHandler"),
        ("sound_wave", "parse_sound_wave", ["SoundWave"], "SoundWaveHandler"),
    ]
    for module, func_name, class_names, handler_name in _optional:
        try:
            mod = __import__(
                f"uasset_read.parsers.asset_types.{module}",
                fromlist=[func_name],
            )
            parse_func = getattr(mod, func_name)
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
