"""FileSystemPackageProvider root containment 校验。"""
import pytest
from pathlib import Path
from uasset_read.package import FileSystemPackageProvider


def test_read_file_outside_root_raises():
    """read_file 应拒绝 root 外路径。"""
    root = Path(__file__).parent
    provider = FileSystemPackageProvider(root)
    with pytest.raises(PermissionError, match="outside root"):
        provider.read_file(str(root / ".." / "README.md"))


def test_open_file_outside_root_raises():
    """open_file 应拒绝 root 外路径。"""
    root = Path(__file__).parent
    provider = FileSystemPackageProvider(root)
    with pytest.raises(PermissionError, match="outside root"):
        provider.open_file(str(root / ".." / "README.md"))


def test_open_package_bundle_outside_root_raises():
    """open_package_bundle 应拒绝 root 外路径。"""
    root = Path(__file__).parent
    provider = FileSystemPackageProvider(root)
    with pytest.raises(PermissionError, match="outside root"):
        provider.open_package_bundle(str(root / ".." / "some.uasset"))


def test_read_file_within_root_ok():
    """read_file 应允许 root 内路径。"""
    root = Path(__file__).parent
    provider = FileSystemPackageProvider(root)
    result = provider.read_file(str(Path(__file__)))
    assert result is not None
