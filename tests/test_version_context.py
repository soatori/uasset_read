"""VersionContext binding-contract tests (G1 §2 target, PR1 A0)."""

import dataclasses
from types import SimpleNamespace

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.exceptions import ParseError
from uasset_read.serializers.package_summary import CustomVersion
from uasset_read.versioning import VersionContext, build_version_context, require_version_context


def test_version_context_field_set_exact():
    names = {f.name for f in dataclasses.fields(VersionContext)}
    assert names == {"file_version_ue4", "file_version_ue5", "custom_versions", "package_layout"}


def test_version_context_frozen():
    ctx = VersionContext(file_version_ue4=522, file_version_ue5=1018)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.file_version_ue4 = 0
    with pytest.raises(TypeError):
        ctx.custom_versions["k"] = 1


def test_require_version_context_missing_raises():
    bare = ByteArchive(b"\x00" * 8)
    with pytest.raises(ParseError) as exc_info:
        require_version_context(bare)
    err = exc_info.value
    assert err.code == "VERSION_CONTEXT_MISSING"
    assert err.diagnostics[0].stage == "package.version_context"


def _stub_summary(*, ue4=522, ue5=1018, custom_versions=()):
    return SimpleNamespace(
        file_version_ue4=ue4,
        file_version_ue5=ue5,
        custom_versions=list(custom_versions),
    )


def test_build_context_fills_from_summary():
    ctx = build_version_context(_stub_summary(ue4=522, ue5=1018))
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
    ctx = build_version_context(summary)
    assert ctx.custom_versions[guid] == 1
