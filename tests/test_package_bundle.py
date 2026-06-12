from __future__ import annotations

from pathlib import Path

from uasset_read.package import (
    ByteArchive,
    IoStorePackageProvider,
    PakPackageProvider,
    PackageArchive,
    open_package_bundle,
)


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
        ByteArchive("A.uasset", b"abcd"),
        ByteArchive("A.uexp", b"efgh"),
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

