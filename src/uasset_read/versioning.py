"""
统一版本管理 — VersionContainer / EUEVersion 枚举。

提供基于 GUID 的版本查询和基于流的版本比较，替代各处 hardcode 的版本判断。
对应 COR-02: FCustomVersion 体系。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List

from uasset_read.constants import (
    FFRAMEWORK_OBJECT_VERSION_GUID,
    FUE5_MAINSTREAM_VERSION_GUID,
    FRELEASE_OBJECT_VERSION_GUID,
    FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
    FBLUEPRINTS_OBJECT_VERSION_GUID,
    FCORE_OBJECT_VERSION_GUID,
    FEDITOR_OBJECT_VERSION_GUID,
    FANIM_OBJECT_VERSION_GUID,
    FPHYSICS_OBJECT_VERSION_GUID,
    FRENDERING_OBJECT_VERSION_GUID,
    UE5_VERSION_MIN,
)


# ============================================================================
# EUEVersion — 语义化版本枚举
# ============================================================================

class EUEVersion(IntEnum):
    """关键 UE 版本阈值，用于 is_at_least() 比较。

    值对应 file_version_ue5（PackageFileSummary.file_version_ue5）。
    UE4 版本使用 file_version_ue4（通常 516-520）。
    """
    # UE4 版本（file_version_ue4 范围）
    UE4_23 = 516     # FFrameworkObjectVersion::Before
    UE4_24 = 517     # FFrameworkObjectVersion::PinTypeContainers
    UE4_25 = 518
    UE4_26 = 519
    UE4_27 = 520

    # UE5 版本（file_version_ue5 范围）
    UE5_0 = 1000     # UE5 initial
    UE5_1 = 1001     # UE5_ADD_SOFTOBJECTPATH_LIST
    UE5_2 = 1005     # UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID
    UE5_3 = 1008     # UE5_ADD_SOFTOBJECTPATH_LIST fully
    UE5_4 = 1010     # UE5_SCRIPT_SERIALIZATION_OFFSET
    UE5_5 = 1012     # UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME
    UE5_6 = 1015     # UE5_VERSE_CELLS
    UE5_7 = 1016     # UE5_PACKAGE_SAVED_HASH


# ============================================================================
# Stream 定义
# ============================================================================

@dataclass(frozen=True)
class VersionStream:
    """一个版本流：GUID + 名称。"""
    guid: str
    name: str


STREAM_FRAMEWORK = VersionStream(FFRAMEWORK_OBJECT_VERSION_GUID, "framework")
STREAM_UE5_MAINSTREAM = VersionStream(FUE5_MAINSTREAM_VERSION_GUID, "ue5_mainstream")
STREAM_RELEASE = VersionStream(FRELEASE_OBJECT_VERSION_GUID, "release")
STREAM_UE5_RELEASE = VersionStream(FUE5RELEASESTREAM_OBJECT_VERSION_GUID, "ue5_release")
STREAM_BLUEPRINTS = VersionStream(FBLUEPRINTS_OBJECT_VERSION_GUID, "blueprints")
STREAM_CORE = VersionStream(FCORE_OBJECT_VERSION_GUID, "core")
STREAM_EDITOR = VersionStream(FEDITOR_OBJECT_VERSION_GUID, "editor")
STREAM_ANIM = VersionStream(FANIM_OBJECT_VERSION_GUID, "anim")
STREAM_PHYSICS = VersionStream(FPHYSICS_OBJECT_VERSION_GUID, "physics")
STREAM_RENDERING = VersionStream(FRENDERING_OBJECT_VERSION_GUID, "rendering")

STREAM_MAP: Dict[str, VersionStream] = {
    "framework": STREAM_FRAMEWORK,
    "ue5_mainstream": STREAM_UE5_MAINSTREAM,
    "release": STREAM_RELEASE,
    "ue5_release": STREAM_UE5_RELEASE,
    "blueprints": STREAM_BLUEPRINTS,
    "core": STREAM_CORE,
    "editor": STREAM_EDITOR,
    "anim": STREAM_ANIM,
    "physics": STREAM_PHYSICS,
    "rendering": STREAM_RENDERING,
}


# ============================================================================
# VersionContainer
# ============================================================================

class _CustomVersionLike:
    """任何具有 guid: str 和 version: int 属性的对象（协议类型）。"""
    guid: str
    version: int


@dataclass
class FPackageFileVersion:
    """UE 文件版本封装（双版本联合比较）。

    对应 UE 的 FPackageFileVersion 结构：
    - FileVersionUE4: int32
    - FileVersionUE5: int32
    """
    file_version_ue4: int = 0
    file_version_ue5: int = 0

    def to_value(self) -> int:
        """返回最高有效版本（UE 源码: FPackageFileVersion::ToValue()）。"""
        if self.file_version_ue5 > 0:
            return self.file_version_ue5
        return self.file_version_ue4

    def __ge__(self, other: int) -> bool:
        """版本比较：是否达到指定阈值。"""
        return self.to_value() >= other

    def __gt__(self, other: int) -> bool:
        """版本比较：是否超过指定阈值。"""
        return self.to_value() > other

    def __le__(self, other: int) -> bool:
        """版本比较：是否低于指定阈值。"""
        return self.to_value() <= other

    def __lt__(self, other: int) -> bool:
        """版本比较：是否未达到指定阈值。"""
        return self.to_value() < other


@dataclass
class VersionContainer:
    """统一版本查询入口。

    从 PackageFileSummary 构建后，提供：
    - get_version(guid) → 查找 CustomVersion 版本号
    - is_at_least(threshold, stream) → 指定流是否达到阈值
    """
    custom_versions: List[_CustomVersionLike] = field(default_factory=list)
    file_version_ue5: int = UE5_VERSION_MIN
    file_version_ue4: int = 0
    _guid_cache: Dict[str, int] = field(default_factory=dict, repr=False)

    @property
    def file_version(self) -> FPackageFileVersion:
        """返回封装的文件版本对象。"""
        return FPackageFileVersion(
            file_version_ue4=self.file_version_ue4,
            file_version_ue5=self.file_version_ue5,
        )

    def get_version(self, guid: str, default: int = 0) -> int:
        """按 GUID 查找版本号，未找到返回 default。

        GUID 比较时自动去除横杠并转小写。
        """
        normalized = guid.replace("-", "").lower()
        cached = self._guid_cache.get(normalized)
        if cached is not None:
            return cached

        for cv in self.custom_versions:
            cv_guid = cv.guid.replace("-", "").lower()
            if cv_guid == normalized:
                self._guid_cache[normalized] = cv.version
                return cv.version

        self._guid_cache[normalized] = default
        return default

    def is_at_least(self, threshold: int, stream: str = "framework") -> bool:
        """检查指定版本流是否达到阈值。

        Args:
            threshold: 目标版本号（或 EUEVersion 枚举值）
            stream: 版本流名称（framework/ue5_mainstream/release/ue5_release）
        """
        stream_def = STREAM_MAP.get(stream)
        if stream_def is None:
            return False
        version = self.get_version(stream_def.guid)
        return version >= threshold

    @property
    def is_ue5(self) -> bool:
        """file_version_ue5 是否在 UE5 范围内。"""
        return self.file_version_ue5 >= UE5_VERSION_MIN


# ============================================================================
# 快捷函数
# ============================================================================

def build_version_container(summary) -> "VersionContainer":
    """从 PackageFileSummary 构建 VersionContainer。

    Args:
        summary: PackageFileSummary 实例，需具有 custom_versions 和 file_version_ue5 属性。
    """
    return VersionContainer(
        custom_versions=summary.custom_versions,
        file_version_ue5=summary.file_version_ue5,
        file_version_ue4=getattr(summary, 'file_version_ue4', 0),
    )
