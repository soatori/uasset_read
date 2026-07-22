"""
统一版本管理 — VersionContainer / EUEVersion 枚举。

提供基于 GUID 的版本查询和基于流的版本比较，替代各处 hardcode 的版本判断。
对应 COR-02: FCustomVersion 体系。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Protocol

from uasset_read.core.utils import normalize_hex_guid

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
    FSEQUENCER_OBJECT_VERSION_GUID,
    FANIMPHYS_OBJECT_VERSION_GUID,
    FDESTRUCTION_OBJECT_VERSION_GUID,
    FEXTERNAL_PHYSICS_OBJECT_VERSION_GUID,
    FENTERPRISE_OBJECT_VERSION_GUID,
    FVR_OBJECT_VERSION_GUID,
    FMOBILE_OBJECT_VERSION_GUID,
    FCINECAMERA_OBJECT_VERSION_GUID,
    FNIAGARA_OBJECT_VERSION_GUID,
    FUE5_SPECIAL_PROJECT_STREAM_OBJECT_VERSION_GUID,
    FRIGVM_OBJECT_VERSION_GUID,
    FCONTROL_RIG_OBJECT_VERSION_GUID,
    FNANITE_RESEARCH_STREAM_OBJECT_VERSION_GUID,
    FSKELETAL_MESH_CUSTOM_VERSION_GUID,
    FNIAGARA_CUSTOM_VERSION_GUID,
    FINTERCHANGE_CUSTOM_VERSION_GUID,
    FASSET_REGISTRY_VERSION_GUID,
    FCURVE_EXPRESSION_CUSTOM_VERSION_GUID,
    UE5_VERSION_MIN,
)


# ============================================================================
# EUEVersion — 语义化版本枚举
# ============================================================================

class EUEVersion(IntEnum):
    """关键 UE 版本阈值，用于版本比较。

    值对应 EUnrealEngineObjectUE5Version 枚举中的 CustomVersion 阈值
    （ObjectVersion.cs），而非 file_version_ue5 的全部可能值。
    file_version_ue5 在包头中存储的是该包引入的最高 CustomVersion 枚举值，
    与本枚举的语义不同。
    UE4 版本使用 file_version_ue4（通常 516-520）。
    """
    # UE4 版本（file_version_ue4 范围）
    UE4_23 = 516     # FFrameworkObjectVersion::Before
    UE4_24 = 517     # FFrameworkObjectVersion::PinTypeContainers
    UE4_25 = 518
    UE4_26 = 519
    UE4_27 = 520

    # UE5 版本（CustomVersion 阈值，对应 EUnrealEngineObjectUE5Version）
    UE5_0 = 1000     # INITIAL_VERSION
    UE5_1 = 1001     # NAMES_REFERENCED_FROM_EXPORT_DATA
    UE5_2 = 1005     # REMOVE_OBJECT_EXPORT_PACKAGE_GUID
    UE5_3 = 1008     # ADD_SOFTOBJECTPATH_LIST
    UE5_4 = 1010     # SCRIPT_SERIALIZATION_OFFSET
    UE5_5 = 1012     # PROPERTY_TAG_COMPLETE_TYPE_NAME
    UE5_6 = 1015     # VERSE_CELLS
    UE5_7 = 1016     # PACKAGE_SAVED_HASH
    UE5_8 = 1018     # IMPORT_TYPE_HIERARCHIES (= AUTOMATIC_VERSION)


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
STREAM_SEQUENCER = VersionStream(FSEQUENCER_OBJECT_VERSION_GUID, "sequencer")
STREAM_ANIMPHYS = VersionStream(FANIMPHYS_OBJECT_VERSION_GUID, "animphys")
STREAM_DESTRUCTION = VersionStream(FDESTRUCTION_OBJECT_VERSION_GUID, "destruction")
STREAM_EXTERNAL_PHYSICS = VersionStream(FEXTERNAL_PHYSICS_OBJECT_VERSION_GUID, "external_physics")
STREAM_ENTERPRISE = VersionStream(FENTERPRISE_OBJECT_VERSION_GUID, "enterprise")
STREAM_VR = VersionStream(FVR_OBJECT_VERSION_GUID, "vr")
STREAM_MOBILE = VersionStream(FMOBILE_OBJECT_VERSION_GUID, "mobile")
STREAM_CINECAMERA = VersionStream(FCINECAMERA_OBJECT_VERSION_GUID, "cinecamera")
STREAM_NIAGARA = VersionStream(FNIAGARA_OBJECT_VERSION_GUID, "niagara")

# Phase 2: P1 核心版本流
STREAM_UE5_SPECIAL_PROJECT = VersionStream(FUE5_SPECIAL_PROJECT_STREAM_OBJECT_VERSION_GUID, "ue5_special_project")
STREAM_RIGVM = VersionStream(FRIGVM_OBJECT_VERSION_GUID, "rigvm")
STREAM_CONTROL_RIG = VersionStream(FCONTROL_RIG_OBJECT_VERSION_GUID, "control_rig")

# Phase 2: P2 特定资产类型版本流
STREAM_NANITE_RESEARCH = VersionStream(FNANITE_RESEARCH_STREAM_OBJECT_VERSION_GUID, "nanite_research")

# Phase 2: P3 插件级版本
STREAM_SKELETAL_MESH_CUSTOM = VersionStream(FSKELETAL_MESH_CUSTOM_VERSION_GUID, "skeletal_mesh_custom")
STREAM_NIAGARA_CUSTOM = VersionStream(FNIAGARA_CUSTOM_VERSION_GUID, "niagara_custom")
STREAM_INTERCHANGE = VersionStream(FINTERCHANGE_CUSTOM_VERSION_GUID, "interchange")
STREAM_ASSET_REGISTRY = VersionStream(FASSET_REGISTRY_VERSION_GUID, "asset_registry")
STREAM_CURVE_EXPRESSION = VersionStream(FCURVE_EXPRESSION_CUSTOM_VERSION_GUID, "curve_expression")

STREAM_MAP: dict[str, VersionStream] = {
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
    "sequencer": STREAM_SEQUENCER,
    "animphys": STREAM_ANIMPHYS,
    "destruction": STREAM_DESTRUCTION,
    "external_physics": STREAM_EXTERNAL_PHYSICS,
    "enterprise": STREAM_ENTERPRISE,
    "vr": STREAM_VR,
    "mobile": STREAM_MOBILE,
    "cinecamera": STREAM_CINECAMERA,
    "niagara": STREAM_NIAGARA,
    "ue5_special_project": STREAM_UE5_SPECIAL_PROJECT,
    "rigvm": STREAM_RIGVM,
    "control_rig": STREAM_CONTROL_RIG,
    "nanite_research": STREAM_NANITE_RESEARCH,
    "skeletal_mesh_custom": STREAM_SKELETAL_MESH_CUSTOM,
    "niagara_custom": STREAM_NIAGARA_CUSTOM,
    "interchange": STREAM_INTERCHANGE,
    "asset_registry": STREAM_ASSET_REGISTRY,
    "curve_expression": STREAM_CURVE_EXPRESSION,
}


# ============================================================================
# VersionContainer
# ============================================================================

class _CustomVersionLike(Protocol):
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
    """
    custom_versions: list[_CustomVersionLike] = field(default_factory=list)
    file_version_ue5: int = UE5_VERSION_MIN
    file_version_ue4: int = 0
    _guid_cache: dict[str, int] = field(default_factory=dict, repr=False)

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
        normalized = normalize_hex_guid(guid)
        cached = self._guid_cache.get(normalized)
        if cached is not None:
            return cached

        for cv in self.custom_versions:
            cv_guid = normalize_hex_guid(cv.guid)
            if cv_guid == normalized:
                self._guid_cache[normalized] = cv.version
                return cv.version

        # 未命中时不缓存 default，避免不同调用者的 default 互相污染
        return default

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
