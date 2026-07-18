"""PackageArchive.read() 边界保护 + package bundle/provider/cache/parse 核心回归测试"""
from __future__ import annotations

import gc
import io
import tempfile
import time
from pathlib import Path

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.package import (
    ByteArchive,
    IoStorePackageProvider,
    PakPackageProvider,
    PackageArchive,
    open_package_bundle,
)


# ---------------------------------------------------------------------------
# PackageArchive.read() 边界保护
# ---------------------------------------------------------------------------

def _make_archive(data: bytes) -> PackageArchive:
    """用 ByteArchive 构造一个最小 PackageArchive。"""
    main = ByteArchive(data, tolerant=False, name="test.uasset")
    return PackageArchive(main, tolerant=False)


def test_read_negative_size_raises():
    """read(-1) 应抛 ParseError 且 tell() 不变。"""
    archive = _make_archive(b"\x00\x01\x02\x03\x04")
    pos_before = archive.tell()
    with pytest.raises(ParseError, match="negative size"):
        archive.read(-1)
    assert archive.tell() == pos_before


def test_read_zero_returns_empty():
    """read(0) 应返回空 bytes，不移动 tell()。"""
    archive = _make_archive(b"\x00\x01\x02")
    result = archive.read(0)
    assert result == b""
    assert archive.tell() == 0


def test_read_normal_returns_data():
    """正常 read 应返回正确数据并推进 tell()。"""
    archive = _make_archive(b"\x00\x01\x02\x03\x04")
    result = archive.read(3)
    assert result == b"\x00\x01\x02"
    assert archive.tell() == 3


def test_read_beyond_eof_raises():
    """read(超过剩余) 应抛 ParseError。"""
    archive = _make_archive(b"\x00\x01")
    with pytest.raises(ParseError, match="Cannot read"):
        archive.read(10)


# ---------------------------------------------------------------------------
# package bundle 测试 (原 test_package_bundle.py)
# ---------------------------------------------------------------------------

def test_filesystem_bundle_discovers_asset_sidecars(tmp_path: Path):
    asset = tmp_path / "A.uasset"
    asset.write_bytes(b"asset")
    (tmp_path / "A.uexp").write_bytes(b"exports")
    (tmp_path / "A.ubulk").write_bytes(b"bulk")
    (tmp_path / "A.uptnl").write_bytes(b"optional")

    bundle = open_package_bundle(str(asset))

    assert bundle.package_kind == "asset"
    assert bundle.container == "filesystem"
    assert set(bundle.package_files) == {".uasset", ".uexp", ".ubulk", ".uptnl"}


def test_filesystem_bundle_supports_umap(tmp_path: Path):
    umap = tmp_path / "Map.umap"
    umap.write_bytes(b"map")

    bundle = open_package_bundle(str(umap))

    assert bundle.package_kind == "map"
    assert set(bundle.package_files) == {".umap"}


def test_package_archive_reads_across_uexp_boundary():
    archive = PackageArchive(
        ByteArchive(b"abcd", name="A.uasset"),
        ByteArchive(b"efgh", name="A.uexp"),
    )

    archive.seek(2)

    assert archive.read(4) == b"cdef"
    assert archive.tell() == 6


class _FakePakReader:
    def __init__(self):
        self.files = {
            "Game/A.uasset": b"asset",
            "Game/A.uexp": b"exports",
        }

    def list_files(self):
        return list(self.files)

    def extract(self, path):
        return self.files.get(path)


def test_pak_provider_loads_bundle_from_virtual_paths():
    provider = PakPackageProvider(_FakePakReader())

    bundle = provider.open_package_bundle("Game/A.uasset")

    assert bundle.container == "pak"
    assert bundle.payloads[".uasset"] == b"asset"
    assert bundle.payloads[".uexp"] == b"exports"


class _Chunk:
    def __init__(self, value: bytes):
        self.bytes = value


class _FakeIoStoreReader:
    def __init__(self):
        self._directory_index = {
            "Game/A.uasset": _Chunk(b"asset_chunk__"),
            "Game/A.uexp": _Chunk(b"exports_chunk"),
        }
        self.data = {
            b"asset_chunk__": b"asset",
            b"exports_chunk": b"exports",
        }

    def list_files(self):
        return list(self._directory_index)

    def extract(self, chunk_id):
        return self.data[chunk_id]


def test_iostore_provider_loads_bundle_from_directory_index():
    provider = IoStorePackageProvider(_FakeIoStoreReader())

    bundle = provider.open_package_bundle("Game/A.uasset")

    assert bundle.container == "iostore"
    assert bundle.payloads[".uasset"] == b"asset"
    assert bundle.payloads[".uexp"] == b"exports"


# ---------------------------------------------------------------------------
# FileSystemPackageProvider 缓存失效测试 (原 test_package_cache.py)
# ---------------------------------------------------------------------------

def test_list_files_cache_returns_same_object():
    """验证缓存返回相同的列表对象。"""
    from uasset_read.package import FileSystemPackageProvider

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.uasset").touch()

        provider = FileSystemPackageProvider(tmpdir)
        result1 = provider.list_files()
        result2 = provider.list_files()

        # 应该返回同一个对象（缓存命中）
        assert result1 is result2


def test_list_files_cache_invalidated_on_file_change():
    """验证文件变化后缓存自动失效。"""
    from uasset_read.package import FileSystemPackageProvider

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test1.uasset").touch()

        provider = FileSystemPackageProvider(tmpdir)
        result1 = provider.list_files()
        assert len(result1) == 1

        # 添加新文件——目录 mtime 变化
        time.sleep(0.1)
        (Path(tmpdir) / "test2.uasset").touch()

        # 缓存应该自动失效
        result2 = provider.list_files()
        assert len(result2) == 2


def test_refresh_file_cache_forces_refresh():
    """验证 refresh_file_cache() 强制刷新缓存。"""
    from uasset_read.package import FileSystemPackageProvider

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test1.uasset").touch()

        provider = FileSystemPackageProvider(tmpdir)
        result1 = provider.list_files()
        assert len(result1) == 1

        # 添加新文件并手动刷新
        (Path(tmpdir) / "test2.uasset").touch()
        provider.refresh_file_cache()

        result2 = provider.list_files()
        assert len(result2) == 2


# ---------------------------------------------------------------------------
# parse_package 核心回归测试 (原 test_parse_package_core.py)
# ---------------------------------------------------------------------------

MAX_PARSE_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def test_parse_package_returns_result():
    """parse_package 应返回有效的 ParseResult。"""
    from uasset_read.parse_uasset import parse_package
    test_assets = list(Path("tests/assets").glob("*.uasset"))[:3]
    for asset_path in test_assets:
        if asset_path.stat().st_size > MAX_PARSE_FILE_SIZE:
            continue
        result = parse_package(str(asset_path))
        assert result.summary is not None
        assert result.name_map is not None
        assert result.export_map is not None
        del result
        gc.collect()


def test_parse_uasset_with_linker_returns_result():
    """parse_uasset_with_linker 应返回有效的 LinkerParseResult。"""
    from uasset_read.parse_uasset import parse_uasset_with_linker
    test_assets = list(Path("tests/assets").glob("*.uasset"))[:3]
    for asset_path in test_assets:
        if asset_path.stat().st_size > MAX_PARSE_FILE_SIZE:
            continue
        result = parse_uasset_with_linker(str(asset_path))
        assert result.summary is not None
        assert result.linker is not None
        assert result.all_objects is not None
        del result
        gc.collect()


def test_parse_package_with_mappings():
    """parse_package 支持 mappings_path 参数。"""
    from uasset_read.parse_uasset import parse_package
    test_assets = list(Path("tests/assets").glob("*.uasset"))[:1]
    if not test_assets:
        pytest.skip("No test assets found")
    result = parse_package(str(test_assets[0]))
    assert "mappings_path" not in result.metadata  # 未提供 mappings


def test_parse_package_aes_key_rejection():
    """parse_package 应拒绝 aes_key 参数。"""
    from uasset_read.parse_uasset import parse_package
    from uasset_read.exceptions import ParseError
    test_assets = list(Path("tests/assets").glob("*.uasset"))[:1]
    if not test_assets:
        pytest.skip("No test assets found")
    result = parse_package(str(test_assets[0]), aes_key=b"\x00" * 16)
    assert not result.is_success
    assert "aes_key" in result.errors[0]
