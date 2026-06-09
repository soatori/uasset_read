"""验证 PackageFileSummary 在版本缺失时保留 UE sentinel 值。"""
import pytest
from uasset_read.serializers.package_summary import PackageFileSummary


def test_sentinel_preload_dependency_default():
    """PreloadDependency 默认值应为 UE sentinel（absent = -1/0）"""
    s = PackageFileSummary(tag=0, legacy_file_version=-5)
    assert s.preload_dependency_count == -1
    assert s.preload_dependency_offset == 0


def test_sentinel_payload_toc_default():
    """PayloadTocOffset 默认值应为 -1（INDEX_NONE）"""
    s = PackageFileSummary(tag=0, legacy_file_version=-5)
    assert s.payload_toc_offset == -1


def test_sentinel_data_resource_default():
    """DataResourceOffset 默认值应为 -1（absent）"""
    s = PackageFileSummary(tag=0, legacy_file_version=-5)
    assert s.data_resource_offset == -1


def test_sentinel_present_but_empty_not_confused():
    """已存在的空表保持 0，不与 absent 混淆"""
    s = PackageFileSummary(tag=0, legacy_file_version=-5)
    s.preload_dependency_count = 0
    assert s.preload_dependency_count == 0
    assert s.preload_dependency_count != -1  # 区分 absent 和 empty


def test_has_preload_dependencies_property():
    """has_preload_dependencies predicate"""
    s = PackageFileSummary(tag=0, legacy_file_version=-5)
    assert not s.has_preload_dependencies  # -1 = absent
    s.preload_dependency_count = 0
    assert s.has_preload_dependencies  # 0 = present but empty


def test_has_payload_toc_property():
    """has_payload_toc predicate"""
    s = PackageFileSummary(tag=0, legacy_file_version=-5)
    assert not s.has_payload_toc  # -1 = absent
    s.payload_toc_offset = 100
    assert s.has_payload_toc  # >0 = present


def test_has_data_resources_property():
    """has_data_resources predicate"""
    s = PackageFileSummary(tag=0, legacy_file_version=-5)
    assert not s.has_data_resources  # -1 = absent
    s.data_resource_offset = 100
    assert s.has_data_resources  # >0 = present
