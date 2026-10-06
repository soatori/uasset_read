"""VersionContext binding-contract tests (G1 §2 target, PR1 A0)."""

import dataclasses
import struct
from types import SimpleNamespace
from typing import cast

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.constants import PKG_FilterEditorOnly
from uasset_read.exceptions import ParseError
from uasset_read.serializers.package_summary import CustomVersion, PackageFileSummary
from uasset_read.versioning import VersionContext, build_version_context, require_version_context


def test_version_context_field_set_exact():
    names = {f.name for f in dataclasses.fields(VersionContext)}
    assert names == {"file_version_ue4", "file_version_ue5", "custom_versions", "package_layout"}


def test_version_context_frozen():
    ctx = VersionContext(file_version_ue4=522, file_version_ue5=1018)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.file_version_ue4 = 0  # pyright: ignore[reportAttributeAccessIssue] -- the frozen violation IS the assertion
    with pytest.raises(TypeError):
        ctx.custom_versions["k"] = 1  # pyright: ignore -- MappingProxyType immutability IS the assertion


def test_require_version_context_missing_raises():
    bare = ByteArchive(b"\x00" * 8)
    with pytest.raises(ParseError) as exc_info:
        require_version_context(bare)
    err = exc_info.value
    assert err.code == "VERSION_CONTEXT_MISSING"
    assert err.diagnostics[0].stage == "package.version_context"


def test_read_property_tag_unmounted_fails_structurally():
    """Step 1: read_property_tag no longer falls back to a silent default."""
    from uasset_read.serializers.property_tags import read_property_tag

    # name index 1, instance 0 -> name_map[1] = "Foo"; no bytes for the tag body.
    archive = ByteArchive(struct.pack("<ii", 1, 0))
    with pytest.raises(ParseError) as exc_info:
        read_property_tag(archive, ["None", "Foo"])
    err = exc_info.value
    assert err.code == "VERSION_CONTEXT_MISSING"
    assert err.diagnostics[0].stage == "package.version_context"


def test_try_recover_property_tag_unmounted_fails_structurally():
    """Step 2: the recovery scanner also requires a mounted context."""
    from uasset_read.parsers.properties.tagged import _try_recover_property_tag

    bare = ByteArchive(b"\x01\x00\x00\x00\x00\x00\x00\x00" * 4)
    with pytest.raises(ParseError) as exc_info:
        _try_recover_property_tag(bare, ["None", "Foo"])
    err = exc_info.value
    assert err.code == "VERSION_CONTEXT_MISSING"
    assert err.diagnostics[0].stage == "package.version_context"


def test_read_import_map_unmounted_fails_structurally():
    """Step 3: threshold readers take versions from the context, not summary."""
    from uasset_read.serializers.object_resources import read_import_map

    summary = SimpleNamespace(
        import_count=0,
        import_offset=0,
        file_version_ue4=522,
        file_version_ue5=1018,
    )
    bare = ByteArchive(b"")
    with pytest.raises(ParseError) as exc_info:
        read_import_map(bare, summary, ["None"])
    err = exc_info.value
    assert err.code == "VERSION_CONTEXT_MISSING"
    assert err.diagnostics[0].stage == "package.version_context"


def test_ftext_dev_notes_filter_editor_only_gate():
    """Step 4/A5-9: dev-notes gate reads Fortnite GUID from the context."""
    from uasset_read.versioning import FORTNITE_GUID, ftext_dev_notes_enabled

    plain = SimpleNamespace(package_flags=0)
    filtered = SimpleNamespace(package_flags=PKG_FilterEditorOnly)
    ctx260 = VersionContext(
        file_version_ue4=522, file_version_ue5=1018, custom_versions={FORTNITE_GUID: 260}
    )
    ctx259 = VersionContext(
        file_version_ue4=522, file_version_ue5=1018, custom_versions={FORTNITE_GUID: 259}
    )
    assert ftext_dev_notes_enabled(filtered, ctx260) is False
    assert ftext_dev_notes_enabled(plain, ctx260) is True
    assert ftext_dev_notes_enabled(plain, ctx259) is False


def test_is_lwc_requires_mounted_context():
    """Step 5: the LWC gate on FKismetArchive reads the mounted context."""
    from uasset_read.constants import UE5_LARGE_WORLD_COORDINATES
    from uasset_read.kismet.archive import FKismetArchive
    from uasset_read.kismet.expressions import _is_lwc

    bare = FKismetArchive(struct.pack("<i", 0), "t", [])
    with pytest.raises(ParseError) as exc_info:
        _is_lwc(bare)
    assert exc_info.value.code == "VERSION_CONTEXT_MISSING"

    mounted = FKismetArchive(struct.pack("<i", 0), "t", [])
    mounted.version_context = VersionContext(
        file_version_ue4=522,
        file_version_ue5=UE5_LARGE_WORLD_COORDINATES,
    )
    assert _is_lwc(mounted) is True
    mounted.version_context = VersionContext(file_version_ue4=522, file_version_ue5=0)
    assert _is_lwc(mounted) is False


def test_property_tag_threshold_both_sides():
    """A5-5: tag format flips exactly at PROPERTY_TAG_COMPLETE_TYPE_NAME."""
    from uasset_read.constants import PROPERTY_TAG_COMPLETE_TYPE_NAME
    from uasset_read.serializers.property_tags import read_property_tag

    name_map = ["None", "Foo", "IntProperty"]

    def _mount(data: bytes, ue5: int) -> ByteArchive:
        archive = ByteArchive(data)
        archive.version_context = VersionContext(file_version_ue4=522, file_version_ue5=ue5)
        return archive

    # Legacy side (threshold - 1): name FName, type FName, size, arrayIndex,
    # hasPropertyGuid u8, propertyExtensions u8 (ue5 >= 1011), 4 value bytes.
    legacy_bytes = (
        struct.pack("<II", 1, 0)
        + struct.pack("<II", 2, 0)
        + struct.pack("<ii", 4, 0)
        + b"\x00"
        + b"\x00"
        + b"\x00\x00\x00\x00"
    )
    legacy_tag = read_property_tag(_mount(legacy_bytes, PROPERTY_TAG_COMPLETE_TYPE_NAME - 1), name_map)
    assert legacy_tag.type == "IntProperty"  # plain type-name string path
    assert legacy_tag.type_parts == []  # no FPropertyTypeName tree

    # New side (threshold + 1): name FName, FPropertyTypeName node (name +
    # inner_count), size, flags u8, 4 value bytes.
    modern_bytes = (
        struct.pack("<II", 1, 0)
        + struct.pack("<II", 2, 0)
        + struct.pack("<i", 0)
        + struct.pack("<i", 4)
        + b"\x00"
        + b"\x00\x00\x00\x00"
    )
    modern_tag = read_property_tag(_mount(modern_bytes, PROPERTY_TAG_COMPLETE_TYPE_NAME + 1), name_map)
    assert modern_tag.type_parts  # FPropertyTypeName tree path
    assert modern_tag.type == "IntProperty"


def _stub_summary(*, ue4=522, ue5=1018, custom_versions=()):
    return SimpleNamespace(
        file_version_ue4=ue4,
        file_version_ue5=ue5,
        custom_versions=list(custom_versions),
    )


def test_build_context_fills_from_summary():
    ctx = build_version_context(cast(PackageFileSummary, _stub_summary(ue4=522, ue5=1018)))
    assert ctx.file_version_ue4 == 522
    assert ctx.file_version_ue5 == 1018
    assert ctx.package_layout == "legacy"
    assert dict(ctx.custom_versions) == {}


def test_build_duplicate_guid_first_wins():
    guid = "86181d60844f64acded316aad6c7ea0d"
    summary = _stub_summary(
        custom_versions=[
            CustomVersion(guid=guid, version=1),
            CustomVersion(guid=guid, version=2),
        ]
    )
    ctx = build_version_context(cast(PackageFileSummary, summary))
    assert ctx.custom_versions[guid] == 1
