"""
VersionContainer 单元测试 — Phase 76 COR-02.

覆盖：
- get_version (GUID 查询, 缺失默认值)
- is_at_least (版本比较, 流切换)
- build_version_container (集成)
- EUEVersion 枚举
"""

import pytest
from uasset_read.versioning import (
    VersionContainer, build_version_container, EUEVersion,
    STREAM_FRAMEWORK, STREAM_UE5_MAINSTREAM, STREAM_RELEASE, STREAM_UE5_RELEASE,
    STREAM_MAP, VersionStream,
)
from uasset_read.constants import (
    FFRAMEWORK_OBJECT_VERSION_GUID,
    FUE5_MAINSTREAM_VERSION_GUID,
    FRELEASE_OBJECT_VERSION_GUID,
    FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
)
from uasset_read.serializers.package_summary import CustomVersion


class TestVersionContainerGetVersion:
    """get_version() — GUID 查找。"""

    def test_exact_guid_match(self):
        cvs = [CustomVersion(guid=FFRAMEWORK_OBJECT_VERSION_GUID.replace("-", "").lower(), version=15)]
        vc = VersionContainer(custom_versions=cvs)
        assert vc.get_version(FFRAMEWORK_OBJECT_VERSION_GUID) == 15

    def test_guid_normalization_removes_dashes(self):
        cvs = [CustomVersion(guid="cffc743f43b04480939114df171d2073", version=19)]
        vc = VersionContainer(custom_versions=cvs)
        assert vc.get_version("CFFC743F-43B04480-939114DF-171D2073") == 19

    def test_guid_case_insensitive(self):
        cvs = [CustomVersion(guid="CFFC743F43B04480939114DF171D2073", version=10)]
        vc = VersionContainer(custom_versions=cvs)
        assert vc.get_version("cffc743f43b04480939114df171d2073") == 10

    def test_missing_guid_returns_default(self):
        vc = VersionContainer()
        assert vc.get_version("nonexistent-guid") == 0
        vc2 = VersionContainer()
        assert vc2.get_version("another-guid", default=-1) == -1

    def test_empty_custom_versions(self):
        vc = VersionContainer(custom_versions=[], file_version_ue5=1016)
        assert vc.get_version(FFRAMEWORK_OBJECT_VERSION_GUID) == 0

    def test_caching(self):
        cvs = [CustomVersion(guid=FFRAMEWORK_OBJECT_VERSION_GUID.replace("-", "").lower(), version=42)]
        vc = VersionContainer(custom_versions=cvs)
        assert vc.get_version(FFRAMEWORK_OBJECT_VERSION_GUID) == 42
        assert vc.get_version(FFRAMEWORK_OBJECT_VERSION_GUID) == 42  # from cache
        assert len(vc._guid_cache) == 1


class TestVersionContainerIsAtLeast:
    """is_at_least() — 版本比较。"""

    def test_framework_at_least_true(self):
        cvs = [CustomVersion(guid=FFRAMEWORK_OBJECT_VERSION_GUID.replace("-", "").lower(), version=20)]
        vc = VersionContainer(custom_versions=cvs)
        assert vc.is_at_least(15, "framework") is True

    def test_framework_at_least_false(self):
        cvs = [CustomVersion(guid=FFRAMEWORK_OBJECT_VERSION_GUID.replace("-", "").lower(), version=10)]
        vc = VersionContainer(custom_versions=cvs)
        assert vc.is_at_least(15, "framework") is False

    def test_unknown_stream_returns_false(self):
        vc = VersionContainer()
        assert vc.is_at_least(100, "nonexistent") is False

    def test_eueversion_enum_value(self):
        cvs = [CustomVersion(guid=FFRAMEWORK_OBJECT_VERSION_GUID.replace("-", "").lower(), version=520)]
        vc = VersionContainer(custom_versions=cvs)
        assert vc.is_at_least(EUEVersion.UE4_27, "framework") is True

    def test_default_stream_is_framework(self):
        cvs = [CustomVersion(guid=FFRAMEWORK_OBJECT_VERSION_GUID.replace("-", "").lower(), version=5)]
        vc = VersionContainer(custom_versions=cvs)
        assert vc.is_at_least(3) is True
        assert vc.is_at_least(10) is False


class TestVersionContainerIsUe5:
    """is_ue5 property."""

    def test_ue5_file(self):
        vc = VersionContainer(file_version_ue5=1016)
        assert vc.is_ue5 is True

    def test_ue4_file(self):
        vc = VersionContainer(file_version_ue5=-9)
        assert vc.is_ue5 is False


class TestBuildVersionContainer:
    """build_version_container() — 从 summary 构建。"""

    def test_build_from_summary(self):
        from uasset_read.serializers.package_summary import PackageFileSummary

        cvs = [CustomVersion(guid=FFRAMEWORK_OBJECT_VERSION_GUID.replace("-", "").lower(), version=19)]
        summary = PackageFileSummary(
            tag=0x9E2A83C1, legacy_file_version=-9,
            file_version_ue5=1016, custom_versions=cvs,
        )
        vc = build_version_container(summary)
        assert isinstance(vc, VersionContainer)
        assert vc.file_version_ue5 == 1016
        assert vc.get_version(FFRAMEWORK_OBJECT_VERSION_GUID) == 19
        assert vc.is_at_least(15, "framework") is True


class TestStreamDefinitions:
    """STREAM_MAP 和 VersionStream 完整性。"""

    def test_all_streams_present(self):
        assert "framework" in STREAM_MAP
        assert "ue5_mainstream" in STREAM_MAP
        assert "release" in STREAM_MAP
        assert "ue5_release" in STREAM_MAP

    def test_stream_guids_match_constants(self):
        assert STREAM_FRAMEWORK.guid == FFRAMEWORK_OBJECT_VERSION_GUID
        assert STREAM_UE5_MAINSTREAM.guid == FUE5_MAINSTREAM_VERSION_GUID
        assert STREAM_RELEASE.guid == FRELEASE_OBJECT_VERSION_GUID
        assert STREAM_UE5_RELEASE.guid == FUE5RELEASESTREAM_OBJECT_VERSION_GUID


class TestEUEVersion:
    """EUEVersion 枚举值。"""

    def test_ue5_0_value(self):
        assert EUEVersion.UE5_0 == 1000

    def test_ue5_7_value(self):
        assert EUEVersion.UE5_7 == 1016

    def test_is_int_enum(self):
        assert isinstance(EUEVersion.UE5_0.value, int)
