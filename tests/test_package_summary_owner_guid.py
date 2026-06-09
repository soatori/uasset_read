"""Task 3: PackageSummary OwnerPersistentGuid 测试 (#46)"""
import pytest
from uasset_read.serializers.package_summary import PackageFileSummary


def test_package_summary_has_owner_persistent_guid_field():
    """PackageFileSummary 包含 owner_persistent_guid 字段"""
    summary = PackageFileSummary(
        tag=0,
        legacy_file_version=-8,
        file_version_ue4=519,
        file_version_ue5=1000,
        file_version_licensee=0,
    )

    assert hasattr(summary, "owner_persistent_guid")
    # 默认值应为空字符串
    assert summary.owner_persistent_guid == ""


def test_package_summary_set_owner_persistent_guid():
    """可以设置 owner_persistent_guid"""
    guid_hex = "a1b2c3d4e5f67890abcdef1234567890"
    summary = PackageFileSummary(
        tag=0,
        legacy_file_version=-8,
        file_version_ue4=519,
        file_version_ue5=1000,
        file_version_licensee=0,
        owner_persistent_guid=guid_hex,
    )

    assert summary.owner_persistent_guid == guid_hex
    assert len(guid_hex) == 32  # 16 bytes = 32 hex chars


def test_package_summary_other_fields_unchanged():
    """验证其他字段未受影响"""
    summary = PackageFileSummary(
        tag=0,
        legacy_file_version=-8,
        file_version_ue4=519,
        file_version_ue5=1000,
        file_version_licensee=0,
        package_name="/Game/TestPackage",
        package_flags=0x1000,
        export_count=10,
        import_count=5,
        persistent_guid="1234567890abcdef1234567890abcdef",
    )

    assert summary.package_name == "/Game/TestPackage"
    assert summary.package_flags == 0x1000
    assert summary.export_count == 10
    assert summary.import_count == 5
    assert summary.persistent_guid == "1234567890abcdef1234567890abcdef"
