"""USubsurfaceProfile 资产类型处理器（opaque partial metadata）。

纯 UPROPERTY 序列化，无自定义 Serialize()。
定义次表面散射材质配置参数。
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_subsurface_profile = make_opaque_stub("SubsurfaceProfile")
