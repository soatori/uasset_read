"""VersionContext binding-contract tests (G1 §2 target, PR1 A0)."""

import dataclasses

import pytest

from uasset_read.versioning import VersionContext


def test_version_context_field_set_exact():
    names = {f.name for f in dataclasses.fields(VersionContext)}
    assert names == {"file_version_ue4", "file_version_ue5", "custom_versions", "package_layout"}


def test_version_context_frozen():
    ctx = VersionContext(file_version_ue4=522, file_version_ue5=1018)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.file_version_ue4 = 0
    with pytest.raises(TypeError):
        ctx.custom_versions["k"] = 1
