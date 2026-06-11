"""验证 CustomVersion GUID 与 UE 源码一致。"""
import pytest
from uasset_read.constants import (
    FCORE_OBJECT_VERSION_GUID,
    FEDITOR_OBJECT_VERSION_GUID,
    FANIM_OBJECT_VERSION_GUID,
    FPHYSICS_OBJECT_VERSION_GUID,
    FRENDERING_OBJECT_VERSION_GUID,
    FBLUEPRINTS_OBJECT_VERSION_GUID,
    FFRAMEWORK_OBJECT_VERSION_GUID,
    FRELEASE_OBJECT_VERSION_GUID,
    FUE5_MAINSTREAM_VERSION_GUID,
    FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
)


def _parse_guid(guid_str: str) -> tuple:
    """解析 GUID 字符串为 (A, B, C, D) 四元组。"""
    parts = guid_str.split("-")
    a = int(parts[0], 16)
    b = int(parts[1], 16)
    c = int(parts[2], 16)
    d = int(parts[3], 16)
    return (a, b, c, d)


class TestCustomVersionGUIDs:
    """验证 CustomVersion GUID 与 UE DevObjectVersion.cpp 一致。"""

    def test_fcore_object_version_guid(self):
        a, b, c, d = _parse_guid(FCORE_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0x375EC13C, 0x06E448FB, 0xB50084F0, 0x262A717E)

    def test_feditor_object_version_guid(self):
        a, b, c, d = _parse_guid(FEDITOR_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0xE4B068ED, 0xF49442E9, 0xA231DA0B, 0x2E46BB41)

    def test_fanim_object_version_guid(self):
        a, b, c, d = _parse_guid(FANIM_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0xAF43A65D, 0x7FD34947, 0x98733E8E, 0xD9C1BB05)

    def test_fphysics_object_version_guid(self):
        a, b, c, d = _parse_guid(FPHYSICS_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0x78F01B33, 0xEBEA4F98, 0xB9B484EA, 0xCCB95AA2)

    def test_frendering_object_version_guid(self):
        a, b, c, d = _parse_guid(FRENDERING_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0x12F88B9F, 0x88754AFC, 0xA67CD90C, 0x383ABD29)

    def test_fblueprints_object_version_guid(self):
        a, b, c, d = _parse_guid(FBLUEPRINTS_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0xB0D832E4, 0x1F894F0D, 0xACCF7EB7, 0x36FD4AA2)

    def test_fframework_object_version_guid(self):
        a, b, c, d = _parse_guid(FFRAMEWORK_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0xCFFC743F, 0x43B04480, 0x939114DF, 0x171D2073)

    def test_frelease_object_version_guid(self):
        a, b, c, d = _parse_guid(FRELEASE_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0x9C54D522, 0xA8264FBE, 0x94210746, 0x61B482D0)

    def test_fue5_mainstream_version_guid(self):
        a, b, c, d = _parse_guid(FUE5_MAINSTREAM_VERSION_GUID)
        assert (a, b, c, d) == (0x697DD581, 0xE64F41AB, 0xAA4A51EC, 0xBEB7B628)

    def test_fue5releasestream_object_version_guid(self):
        a, b, c, d = _parse_guid(FUE5RELEASESTREAM_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0xD89B5E42, 0x24BD4D46, 0x8412ACA8, 0xDF641779)
