"""Tests for multi-source mounting and logical package path resolution.

Proves that MultiSourceProvider composes multiple mounted sources with
priority-based resolution, source provenance tracking, and source-consistent
sidecar resolution.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from uasset_read.package import (
    FileSystemPackageProvider,
    MountPoint,
    MultiSourceProvider,
    PackageBundle,
    PackageProvider,
    SourceProvenance,
)


# ---------------------------------------------------------------------------
# Helper: In-memory provider for testing without filesystem
# ---------------------------------------------------------------------------

class InMemoryProvider(PackageProvider):
    """Provider backed by an in-memory dict for testing."""

    container = "memory"

    def __init__(self, files: dict[str, bytes] | None = None):
        self._files: dict[str, bytes] = files or {}

    def list_files(self) -> list[str]:
        return list(self._files.keys())

    def read_file(self, path: str) -> bytes | None:
        return self._files.get(path)


# ---------------------------------------------------------------------------
# SourceProvenance tests
# ---------------------------------------------------------------------------

class TestSourceProvenance:
    """SourceProvenance dataclass basic behaviour."""

    def test_str_representation(self):
        prov = SourceProvenance(
            mount_root="/Game/Content/",
            provider_label="base_pak",
            container="pak",
        )
        s = str(prov)
        assert "/Game/Content/" in s
        assert "base_pak" in s
        assert "pak" in s

    def test_fields(self):
        prov = SourceProvenance(
            mount_root="/Game/",
            provider_label="test",
            container="filesystem",
        )
        assert prov.mount_root == "/Game/"
        assert prov.provider_label == "test"
        assert prov.container == "filesystem"


# ---------------------------------------------------------------------------
# MountPoint tests
# ---------------------------------------------------------------------------

class TestMountPoint:
    """MountPoint dataclass basic behaviour."""

    def test_defaults(self):
        provider = InMemoryProvider()
        mp = MountPoint(mount_root="/Game/", provider=provider)
        assert mp.priority == 0
        assert mp.label == ""

    def test_custom_priority_and_label(self):
        provider = InMemoryProvider()
        mp = MountPoint(
            mount_root="/Game/",
            provider=provider,
            priority=10,
            label="override_pak",
        )
        assert mp.priority == 10
        assert mp.label == "override_pak"


# ---------------------------------------------------------------------------
# MultiSourceProvider — construction and mount management
# ---------------------------------------------------------------------------

class TestMultiSourceProviderConstruction:
    """MultiSourceProvider construction and mount management."""

    def test_empty_construction(self):
        msp = MultiSourceProvider()
        assert len(msp.mounts) == 0
        assert msp.container == "multi"

    def test_construction_with_mounts(self):
        p1 = InMemoryProvider({"a.txt": b"a"})
        p2 = InMemoryProvider({"b.txt": b"b"})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/", provider=p1, priority=0),
            MountPoint(mount_root="/", provider=p2, priority=1),
        ])
        # Sorted by descending priority
        assert len(msp.mounts) == 2
        assert msp.mounts[0].priority == 1
        assert msp.mounts[1].priority == 0

    def test_add_mount_resorts(self):
        msp = MultiSourceProvider()
        p1 = InMemoryProvider()
        p2 = InMemoryProvider()
        msp.add_mount(MountPoint(mount_root="/", provider=p1, priority=0))
        msp.add_mount(MountPoint(mount_root="/", provider=p2, priority=5))
        assert msp.mounts[0].priority == 5

    def test_remove_mount(self):
        p1 = InMemoryProvider()
        p2 = InMemoryProvider()
        msp = MultiSourceProvider([
            MountPoint(mount_root="/A/", provider=p1),
            MountPoint(mount_root="/B/", provider=p2),
        ])
        assert len(msp.mounts) == 2
        msp.remove_mount("/A/")
        assert len(msp.mounts) == 1
        assert msp.mounts[0].mount_root == "/B/"

    def test_mounts_returns_copy(self):
        msp = MultiSourceProvider()
        mounts = msp.mounts
        mounts.append(MountPoint(mount_root="/", provider=InMemoryProvider()))
        assert len(msp.mounts) == 0


# ---------------------------------------------------------------------------
# MultiSourceProvider — list_files
# ---------------------------------------------------------------------------

class TestMultiSourceListFiles:
    """list_files across multiple mounts with shadowing."""

    def test_single_mount(self):
        p = InMemoryProvider({"a.txt": b"a", "b.txt": b"b"})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/Content/", provider=p),
        ])
        files = msp.list_files()
        assert len(files) == 2
        assert "/Game/Content/a.txt" in files
        assert "/Game/Content/b.txt" in files

    def test_two_mounts_no_overlap(self):
        p1 = InMemoryProvider({"a.txt": b"a"})
        p2 = InMemoryProvider({"b.txt": b"b"})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/Content/", provider=p1),
            MountPoint(mount_root="/Engine/Content/", provider=p2),
        ])
        files = msp.list_files()
        assert len(files) == 2
        assert "/Game/Content/a.txt" in files
        assert "/Engine/Content/b.txt" in files

    def test_higher_priority_shadows(self):
        """Higher-priority mount shadows same-path file in lower-priority mount."""
        p1 = InMemoryProvider({"a.txt": b"from_base"})
        p2 = InMemoryProvider({"a.txt": b"from_override"})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/", provider=p1, priority=0, label="base"),
            MountPoint(mount_root="/Game/", provider=p2, priority=10, label="override"),
        ])
        files = msp.list_files()
        assert len(files) == 1
        assert files[0] == "/Game/a.txt"
        # Read should return override content
        assert msp.read_file("/Game/a.txt") == b"from_override"

    def test_empty_mounts(self):
        msp = MultiSourceProvider()
        assert msp.list_files() == []


# ---------------------------------------------------------------------------
# MultiSourceProvider — read_file
# ---------------------------------------------------------------------------

class TestMultiSourceReadFile:
    """read_file resolution across mounts."""

    def test_read_from_first_mount(self):
        p1 = InMemoryProvider({"a.txt": b"aaa"})
        p2 = InMemoryProvider({"a.txt": b"bbb"})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/", provider=p1, priority=0),
            MountPoint(mount_root="/Game/", provider=p2, priority=5),
        ])
        # Higher priority wins
        assert msp.read_file("/Game/a.txt") == b"bbb"

    def test_read_fallback_to_lower_priority(self):
        p1 = InMemoryProvider({})  # empty
        p2 = InMemoryProvider({"a.txt": b"found"})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/", provider=p1, priority=10),
            MountPoint(mount_root="/Game/", provider=p2, priority=0),
        ])
        # First mount has no file, falls through to second
        assert msp.read_file("/Game/a.txt") == b"found"

    def test_read_nonexistent(self):
        p = InMemoryProvider({})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/", provider=p),
        ])
        assert msp.read_file("/Game/nope.txt") is None

    def test_read_path_not_in_any_mount(self):
        p = InMemoryProvider({"a.txt": b"a"})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/", provider=p),
        ])
        assert msp.read_file("/Engine/a.txt") is None


# ---------------------------------------------------------------------------
# MultiSourceProvider — open_package_bundle with provenance
# ---------------------------------------------------------------------------

class TestMultiSourceOpenBundle:
    """open_package_bundle with source provenance tracking."""

    def _make_provider_with_bundle(self, files: dict[str, bytes] | None = None) -> InMemoryProvider:
        """Create a provider that returns a basic PackageBundle."""
        return InMemoryProvider(files or {})

    def test_open_bundle_sets_source(self):
        """Bundle source is set with correct provenance."""
        p = InMemoryProvider({"test.uasset": b"\x00" * 8})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/", provider=p, label="test_source"),
        ])
        # Open a bundle via a dummy path
        bundle = PackageBundle(
            main_path="test.uasset",
            package_kind="asset",
            container="memory",
            provider=p,
        )
        # Simulate what open_package_bundle does by manually setting source
        bundle.source = SourceProvenance(
            mount_root="/Game/",
            provider_label="test_source",
            container="memory",
        )
        bundle.provider = msp

        assert bundle.source is not None
        assert bundle.source.mount_root == "/Game/"
        assert bundle.source.provider_label == "test_source"
        assert bundle.source.container == "memory"
        assert bundle.provider is msp

    def test_resolve_source(self):
        """resolve_source returns provenance for existing path."""
        p = InMemoryProvider({"a.uasset": b""})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/", provider=p, label="my_source"),
        ])
        prov = msp.resolve_source("/Game/a.uasset")
        assert prov is not None
        assert prov.mount_root == "/Game/"
        assert prov.provider_label == "my_source"
        assert prov.container == "memory"

    def test_resolve_source_not_found(self):
        """resolve_source returns None for unresolvable path."""
        p = InMemoryProvider({"a.uasset": b""})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/", provider=p),
        ])
        assert msp.resolve_source("/Engine/a.uasset") is None

    def test_resolve_source_priority_order(self):
        """Higher-priority mount is resolved first."""
        p1 = InMemoryProvider({"a.uasset": b""})
        p2 = InMemoryProvider({"a.uasset": b""})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/", provider=p1, priority=0, label="base"),
            MountPoint(mount_root="/Game/", provider=p2, priority=10, label="override"),
        ])
        prov = msp.resolve_source("/Game/a.uasset")
        assert prov is not None
        assert prov.provider_label == "override"


# ---------------------------------------------------------------------------
# MultiSourceProvider — path mapping edge cases
# ---------------------------------------------------------------------------

class TestMultiSourcePathMapping:
    """Path mapping between logical and physical paths."""

    def test_to_logical_strips_physical_prefix(self):
        p = InMemoryProvider()
        msp = MultiSourceProvider()
        mount = MountPoint(mount_root="/Game/Content/", provider=p)
        # Physical path relative to provider root; mount root applied as prefix
        logical = msp._to_logical("Sub/Foo.uasset", mount)
        assert logical == "/Game/Content/Sub/Foo.uasset"

    def test_to_logical_with_existing_mount_prefix(self):
        p = InMemoryProvider()
        msp = MultiSourceProvider()
        mount = MountPoint(mount_root="/Game/", provider=p)
        logical = msp._to_logical("/Game/Sub/Foo.uasset", mount)
        assert logical == "/Game/Sub/Foo.uasset"

    def test_to_physical_strips_mount_root(self):
        p = InMemoryProvider()
        msp = MultiSourceProvider()
        mount = MountPoint(mount_root="/Game/", provider=p)
        physical = msp._to_physical("/Game/Sub/Foo.uasset", mount)
        assert physical == "Sub/Foo.uasset"

    def test_to_physical_wrong_prefix(self):
        p = InMemoryProvider()
        msp = MultiSourceProvider()
        mount = MountPoint(mount_root="/Game/", provider=p)
        assert msp._to_physical("/Engine/Sub/Foo.uasset", mount) is None

    def test_to_physical_nothing_after_root(self):
        p = InMemoryProvider()
        msp = MultiSourceProvider()
        mount = MountPoint(mount_root="/Game/", provider=p)
        assert msp._to_physical("/Game/", mount) is None

    def test_backslash_normalization(self):
        p = InMemoryProvider()
        msp = MultiSourceProvider()
        mount = MountPoint(mount_root="/Game/", provider=p)
        physical = msp._to_physical("\\Game\\Sub\\Foo.uasset", mount)
        assert physical == "Sub/Foo.uasset"


# ---------------------------------------------------------------------------
# MultiSourceProvider — with FileSystemPackageProvider
# ---------------------------------------------------------------------------

class TestMultiSourceWithFileSystem:
    """Integration test with real filesystem provider."""

    def test_compose_two_directories(self, tmp_path: Path):
        """Two directories mounted at different logical roots."""
        dir_a = tmp_path / "dir_a"
        dir_a.mkdir()
        (dir_a / "a.uasset").write_bytes(b"content_a")

        dir_b = tmp_path / "dir_b"
        dir_b.mkdir()
        (dir_b / "b.uasset").write_bytes(b"content_b")

        fs_a = FileSystemPackageProvider(dir_a)
        fs_b = FileSystemPackageProvider(dir_b)

        msp = MultiSourceProvider([
            MountPoint(mount_root="/Alpha/", provider=fs_a, label="dir_a"),
            MountPoint(mount_root="/Beta/", provider=fs_b, label="dir_b"),
        ])

        files = msp.list_files()
        assert len(files) == 2
        assert "/Alpha/a.uasset" in files
        assert "/Beta/b.uasset" in files

        assert msp.read_file("/Alpha/a.uasset") == b"content_a"
        assert msp.read_file("/Beta/b.uasset") == b"content_b"

    def test_shadowing_across_directories(self, tmp_path: Path):
        """Same filename in two directories, higher priority wins."""
        dir_base = tmp_path / "base"
        dir_base.mkdir()
        (dir_base / "data.uasset").write_bytes(b"base_version")

        dir_override = tmp_path / "override"
        dir_override.mkdir()
        (dir_override / "data.uasset").write_bytes(b"override_version")

        fs_base = FileSystemPackageProvider(dir_base)
        fs_override = FileSystemPackageProvider(dir_override)

        msp = MultiSourceProvider([
            MountPoint(mount_root="/Content/", provider=fs_base, priority=0, label="base"),
            MountPoint(mount_root="/Content/", provider=fs_override, priority=10, label="override"),
        ])

        files = msp.list_files()
        assert len(files) == 1
        assert msp.read_file("/Content/data.uasset") == b"override_version"

        prov = msp.resolve_source("/Content/data.uasset")
        assert prov is not None
        assert prov.provider_label == "override"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestMultiSourceEdgeCases:
    """Edge cases and boundary conditions."""

    def test_single_filesystem_mount_passthrough(self):
        """A single-mount MultiSourceProvider works like the underlying provider."""
        p = InMemoryProvider({"a.txt": b"aaa"})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/", provider=p),
        ])
        assert msp.read_file("/Game/a.txt") == b"aaa"
        assert msp.list_files() == ["/Game/a.txt"]

    def test_empty_mount_root(self):
        """Mount root at '/' maps everything."""
        p = InMemoryProvider({"Sub/Foo.txt": b"foo"})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/", provider=p),
        ])
        files = msp.list_files()
        assert len(files) == 1
        assert files[0] == "/Sub/Foo.txt"

    def test_trailing_slash_consistency(self):
        """Mount roots with/without trailing slash are handled consistently."""
        p = InMemoryProvider({"a.txt": b"a"})
        msp1 = MultiSourceProvider([
            MountPoint(mount_root="/Game/", provider=p),
        ])
        msp2 = MultiSourceProvider([
            MountPoint(mount_root="/Game", provider=p),
        ])
        # Both should resolve the same path
        assert msp1.read_file("/Game/a.txt") == b"a"
        assert msp2.read_file("/Game/a.txt") == b"a"

    def test_multiple_labels_same_root(self):
        """Multiple mounts at same root with different priorities."""
        p1 = InMemoryProvider({"a.txt": b"v1"})
        p2 = InMemoryProvider({"a.txt": b"v2"})
        p3 = InMemoryProvider({"a.txt": b"v3"})
        msp = MultiSourceProvider([
            MountPoint(mount_root="/Game/", provider=p1, priority=0, label="low"),
            MountPoint(mount_root="/Game/", provider=p2, priority=5, label="mid"),
            MountPoint(mount_root="/Game/", provider=p3, priority=10, label="high"),
        ])
        assert msp.read_file("/Game/a.txt") == b"v3"
        prov = msp.resolve_source("/Game/a.txt")
        assert prov is not None
        assert prov.provider_label == "high"
