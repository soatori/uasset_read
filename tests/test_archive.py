"""Tests for archive attribute parity across FArchive subclasses (#464)."""


class TestArchiveSubclassAttributeParity:
    """#464: FArchive subclasses must have all parent attributes after init."""

    def test_byte_archive_has_all_parent_attrs(self):
        from uasset_read.archive import ByteArchive
        ba = ByteArchive(b"\x00" * 100, name="test")
        assert hasattr(ba, "_diagnostics")
        assert hasattr(ba, "_name_warnings_seen")
        assert hasattr(ba, "_hex_view_enabled")
        assert hasattr(ba, "_hex_view_entries")
        assert hasattr(ba, "_hex_view_context")
        assert hasattr(ba, "_logger")
        assert hasattr(ba, "_name_map")

    def test_package_archive_has_all_parent_attrs(self):
        from uasset_read.archive import ByteArchive
        from uasset_read.package import PackageArchive
        main = ByteArchive(b"\x00" * 100, name="test.uasset")
        pa = PackageArchive(main)
        assert hasattr(pa, "_diagnostics")
        assert hasattr(pa, "_name_warnings_seen")
        assert hasattr(pa, "_hex_view_enabled")
        assert hasattr(pa, "_hex_view_entries")
        assert hasattr(pa, "_hex_view_context")
        assert hasattr(pa, "_logger")

    def test_kismet_archive_has_all_parent_attrs(self):
        from uasset_read.kismet.archive import FKismetArchive
        ka = FKismetArchive(b"\x00" * 100, name="test", name_map=[])
        assert hasattr(ka, "_diagnostics")
        assert hasattr(ka, "_name_warnings_seen")
        assert hasattr(ka, "_hex_view_enabled")
        assert hasattr(ka, "_hex_view_entries")
        assert hasattr(ka, "_hex_view_context")
        assert hasattr(ka, "_logger")
        assert hasattr(ka, "_name_map")
