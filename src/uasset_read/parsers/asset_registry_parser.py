"""AssetRegistryData 解析器 — 提取资产元数据标签。

解析 UE 资产文件中的 AssetRegistryData 区段，提取：
- ObjectPath：对象路径
- ObjectClassName：对象类名
- Tags：键值对标签列表

数据格式（UE 源码参考：PackageReader.cpp ReadPackageDataMain）：
- DependencyDataOffset (int64, 仅非 Cooked 且版本 >= VER_UE4_ASSETREGISTRY_DEPENDENCYFLAGS)
- ObjectCount (int32)
- 对每个 object:
  - ObjectPath (FString)
  - ObjectClassName (FString)
  - TagCount (int32)
  - 对每个 tag:
    - Key (FString)
    - Value (FString)
"""

import logging
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional



logger = logging.getLogger(__name__)


@dataclass
class AssetRegistryTag:
    """单个资产标签（键值对）。"""
    key: str
    value: str


@dataclass
class AssetRegistryObjectData:
    """单个对象的资产注册表数据。"""
    object_path: str
    object_class_name: str
    tags: List[AssetRegistryTag] = field(default_factory=list)

    def tags_as_dict(self) -> Dict[str, str]:
        """将标签列表转换为字典。"""
        return {tag.key: tag.value for tag in self.tags}


@dataclass
class AssetRegistryData:
    """AssetRegistryData 解析结果。"""
    dependency_data_offset: int = 0
    objects: List[AssetRegistryObjectData] = field(default_factory=list)

    @property
    def object_count(self) -> int:
        return len(self.objects)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 序列化）。"""
        return {
            "dependency_data_offset": self.dependency_data_offset,
            "object_count": self.object_count,
            "objects": [
                {
                    "object_path": obj.object_path,
                    "object_class_name": obj.object_class_name,
                    "tags": obj.tags_as_dict(),
                }
                for obj in self.objects
            ],
        }


def read_asset_registry_data(
    archive: Any,
    asset_registry_data_offset: int,
    file_version_ue4: int = 0,
    is_cooked: bool = False,
) -> Optional[AssetRegistryData]:
    """读取 AssetRegistryData。

    Args:
        archive: FArchive 实例
        asset_registry_data_offset: AssetRegistryData 在文件中的偏移
        file_version_ue4: UE4 文件版本号
        is_cooked: 是否为 Cooked 包

    Returns:
        AssetRegistryData 实例，或 None（偏移为 0 或读取失败时）
    """
    if asset_registry_data_offset <= 0:
        return None

    try:
        archive.seek(asset_registry_data_offset)
    except (OSError, OverflowError) as e:
        logger.debug("无法定位到 AssetRegistryDataOffset=%d: %s", asset_registry_data_offset, e)
        return None

    result = AssetRegistryData()

    try:
        # VER_UE4_ASSETREGISTRY_DEPENDENCYFLAGS = 510
        # 非 Cooked 且版本 >= 510 时读取 DependencyDataOffset
        # UE 写入时使用 int64（见 SavePackageUtilities.cpp:1684、IAssetRegistry.h:1366）
        # 部分资产（如 pre-dependency 格式保存的编辑器资产）不包含此字段，
        # 通过验证偏移值合理性来检测格式差异
        if not is_cooked and file_version_ue4 >= 510:
            pos_before = archive.tell()
            dep_offset_64 = archive.read_i64()
            # 合理性校验：偏移应为 -1（INDEX_NONE）、0、或不超过文件大小
            file_size = archive.total_size()
            if dep_offset_64 < -1 or (dep_offset_64 > 0 and file_size > 0 and dep_offset_64 > file_size):
                # 值不合理 — 可能是 pre-dependency 格式（无此字段），
                # 回退 8 字节，将 object_count 重新读为 int32
                archive.seek(pos_before)
                result.dependency_data_offset = -1
                logger.debug(
                    "AssetRegistryData: DependencyDataOffset=%d 超出文件范围 "
                    "(file_size=%d)，疑似 pre-dependency 格式，跳过此字段",
                    dep_offset_64, file_size,
                )
            else:
                result.dependency_data_offset = dep_offset_64
        else:
            result.dependency_data_offset = -1

        # 读取 ObjectCount
        object_count = archive.read_i32()
        if object_count < 0:
            logger.debug("AssetRegistryData: ObjectCount 为负数 (%d)，跳过", object_count)
            return result

        # 安全检查：object_count 不能过大
        file_size = archive.total_size()
        if file_size > 0 and object_count > file_size:
            logger.debug(
                "AssetRegistryData: ObjectCount=%d 明显过大（文件大小=%d），跳过",
                object_count, file_size,
            )
            return result

        for _ in range(object_count):
            obj_data = _read_object_data(archive)
            if obj_data is not None:
                result.objects.append(obj_data)

    except (struct.error, OSError, ValueError) as e:
        logger.debug("AssetRegistryData 解析异常: %s", e)
        # 返回已解析的部分数据
        return result

    return result


def _read_object_data(archive: Any) -> Optional[AssetRegistryObjectData]:
    """读取单个对象的资产注册表数据。"""
    try:
        object_path = archive.read_fstring()
        object_class_name = archive.read_fstring()
        tag_count = archive.read_i32()

        if tag_count < 0:
            logger.debug("AssetRegistryData: TagCount 为负数 (%d)，跳过对象", tag_count)
            return None

        tags: List[AssetRegistryTag] = []
        for _ in range(tag_count):
            key = archive.read_fstring()
            value = archive.read_fstring()
            if key or value:
                tags.append(AssetRegistryTag(key=key, value=value))

        return AssetRegistryObjectData(
            object_path=object_path or "",
            object_class_name=object_class_name or "",
            tags=tags,
        )

    except (struct.error, OSError, ValueError) as e:
        logger.debug("AssetRegistryData: 读取对象数据异常: %s", e)
        return None
