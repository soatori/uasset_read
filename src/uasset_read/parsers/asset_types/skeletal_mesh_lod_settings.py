"""USkeletalMeshLODSettings 资产类型处理器（opaque partial metadata）。

USkeletalMeshLODSettings 的 Serialize() 仅调用 Super::Serialize()，
数据通过 UPROPERTY 序列化。但当前通用 tagged property parser
无法完整解析其 payload，因此作为 opaque stub 提供类型识别。
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_skeletal_mesh_lod_settings = make_opaque_stub("SkeletalMeshLODSettings")
