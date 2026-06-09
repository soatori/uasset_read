"""Tests for PackageFileSummary deprecated array fields (#46)."""
import pytest
from uasset_read.serializers.package_summary import PackageFileSummary


def test_compressed_chunks_default_empty():
    """compressed_chunks 默认为空列表。"""
    summary = PackageFileSummary(tag=0, legacy_file_version=-8, file_version_ue4=519)
    assert summary.compressed_chunks == []
    assert isinstance(summary.compressed_chunks, list)


def test_additional_packages_default_empty():
    """additional_packages_to_cook 默认为空列表。"""
    summary = PackageFileSummary(tag=0, legacy_file_version=-8, file_version_ue4=519)
    assert summary.additional_packages_to_cook == []
    assert isinstance(summary.additional_packages_to_cook, list)


def test_compressed_chunks_stores_values():
    """compressed_chunks 可存储 chunk 字典。"""
    chunks = [
        {
            "uncompressed_offset": 0,
            "uncompressed_size": 1024,
            "compressed_offset": 0,
            "compressed_size": 512,
        }
    ]
    summary = PackageFileSummary(
        tag=0, legacy_file_version=-8, file_version_ue4=519,
        compressed_chunks=chunks,
    )
    assert len(summary.compressed_chunks) == 1
    assert summary.compressed_chunks[0]["uncompressed_size"] == 1024
    assert summary.compressed_chunks[0]["compressed_size"] == 512


def test_additional_packages_stores_values():
    """additional_packages_to_cook 可存储包名列表。"""
    packages = ["/Game/Maps/Level1", "/Game/Maps/Level2"]
    summary = PackageFileSummary(
        tag=0, legacy_file_version=-8, file_version_ue4=519,
        additional_packages_to_cook=packages,
    )
    assert summary.additional_packages_to_cook == packages


def test_owner_persistent_guid_still_works():
    """owner_persistent_guid 字段不受新增字段影响。"""
    summary = PackageFileSummary(
        tag=0, legacy_file_version=-8, file_version_ue4=519,
        owner_persistent_guid="a1b2c3d4e5f67890abcdef1234567890",
    )
    assert summary.owner_persistent_guid == "a1b2c3d4e5f67890abcdef1234567890"
    assert summary.compressed_chunks == []
    assert summary.additional_packages_to_cook == []
