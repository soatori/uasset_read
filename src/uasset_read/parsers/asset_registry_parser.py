"""AssetRegistryData parser -- extract asset metadata tags.

Parses the AssetRegistryData section in UE asset files, extracting:
- ObjectPath: object path
- ObjectClassName: object class name
- Tags: key-value tag list

Data format (UE source reference: PackageReader.cpp ReadPackageDataMain):
- DependencyDataOffset (int64, only non-Cooked and version >= VER_UE4_ASSETREGISTRY_DEPENDENCYFLAGS)
- ObjectCount (int32)
- For each object:
  - ObjectPath (FString)
  - ObjectClassName (FString)
  - TagCount (int32)
  - For each tag:
    - Key (FString)
    - Value (FString)
"""

import logging
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from uasset_read.constants import UE4_ASSETREGISTRY_DEPENDENCYFLAGS
from uasset_read.exceptions import ParseError


logger = logging.getLogger(__name__)


@dataclass
class AssetRegistryTag:
    """Single asset tag (key-value pair)."""

    key: str
    value: str


@dataclass
class AssetRegistryObjectData:
    """Asset registry data for a single object."""

    object_path: str
    object_class_name: str
    tags: List[AssetRegistryTag] = field(default_factory=list)

    def tags_as_dict(self) -> Dict[str, str]:
        """Convert tag list to dictionary."""
        return {tag.key: tag.value for tag in self.tags}


@dataclass
class AssetRegistryData:
    """AssetRegistryData parse result."""

    dependency_data_offset: int = 0
    objects: List[AssetRegistryObjectData] = field(default_factory=list)
    corrupted: bool = False
    """True when the data was only partially parsed due to malformed input."""

    @property
    def object_count(self) -> int:
        return len(self.objects)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (for JSON serialization)."""
        d = {
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
        if self.corrupted:
            d["corrupted"] = True
        return d


def read_asset_registry_data(
    archive: Any,
    asset_registry_data_offset: int,
    file_version_ue4: int = 0,
    is_cooked: bool = False,
) -> Optional[AssetRegistryData]:
    """Read AssetRegistryData.

    Args:
        archive: FArchive instance
        asset_registry_data_offset: AssetRegistryData offset in file
        file_version_ue4: UE4 file version
        is_cooked: whether this is a Cooked package

    Returns:
        AssetRegistryData instance, or None (if offset is 0 or read fails)
    """
    if asset_registry_data_offset <= 0:
        return None

    try:
        archive.seek(asset_registry_data_offset)
    except (OSError, OverflowError) as e:
        logger.debug("Cannot locate AssetRegistryDataOffset=%d: %s", asset_registry_data_offset, e)
        return None

    result = AssetRegistryData()

    try:
        # VER_UE4_ASSETREGISTRY_DEPENDENCYFLAGS = 521 (project frozen numbering)
        # UE reads DependencyDataOffset when not cooked and version >= 521
        # (PackageReader.cpp: operator<< guards on that version; SavePackageUtilities writes int64).
        # Some assets (e.g. editor assets saved in pre-dependency format) do not include this field;
        # detect format differences by validating the offset value reasonableness
        if not is_cooked and file_version_ue4 >= UE4_ASSETREGISTRY_DEPENDENCYFLAGS:
            pos_before = archive.tell()
            dep_offset_64 = archive.read_i64()
            # Reasonableness check: offset should be -1 (INDEX_NONE), 0, or not exceed file size
            file_size = archive.total_size()
            if dep_offset_64 < -1 or (dep_offset_64 > 0 and file_size > 0 and dep_offset_64 > file_size):
                # Value is unreasonable -- likely pre-dependency format (no such field);
                # rewind 8 bytes and re-read object_count as int32
                archive.seek(pos_before)
                result.dependency_data_offset = -1
                logger.debug(
                    "AssetRegistryData: DependencyDataOffset=%d exceeds file bounds "
                    "(file_size=%d), likely pre-dependency format, skipping this field",
                    dep_offset_64,
                    file_size,
                )
            else:
                result.dependency_data_offset = dep_offset_64
        else:
            result.dependency_data_offset = -1

        # Read ObjectCount
        object_count = archive.read_i32()
        if object_count < 0:
            logger.debug("AssetRegistryData: ObjectCount is negative (%d), skipping", object_count)
            return result

        # Safety check: object_count must not be too large
        file_size = archive.total_size()
        if file_size > 0 and object_count > file_size:
            logger.debug(
                "AssetRegistryData: ObjectCount=%d is clearly too large (file_size=%d), skipping",
                object_count,
                file_size,
            )
            return result

        for _ in range(object_count):
            obj_data = _read_object_data(archive)
            if obj_data is not None:
                result.objects.append(obj_data)
            else:
                # _read_object_data returned None — object could not be read
                # (truncated data, malformed fields, etc.). Flag corruption.
                result.corrupted = True

    except (struct.error, OSError, ValueError, ParseError) as e:
        logger.debug("AssetRegistryData parse exception: %s", e)
        # Return partially parsed data and mark as corrupted
        result.corrupted = True
        return result

    return result


def _read_object_data(archive: Any) -> Optional[AssetRegistryObjectData]:
    """Read asset registry data for a single object."""
    try:
        object_path = archive.read_fstring()
        object_class_name = archive.read_fstring()
        tag_count = archive.read_i32()

        if tag_count < 0:
            logger.debug("AssetRegistryData: TagCount is negative (%d), skipping object", tag_count)
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

    except (struct.error, OSError, ValueError, ParseError) as e:
        logger.debug("AssetRegistryData: exception reading object data: %s", e)
        return None
