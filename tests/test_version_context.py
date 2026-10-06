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
