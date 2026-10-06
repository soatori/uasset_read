"""VersionContext binding-contract tests (G1 §2 target, PR1 A0)."""

import dataclasses

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.exceptions import ParseError
from uasset_read.versioning import VersionContext, require_version_context


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
