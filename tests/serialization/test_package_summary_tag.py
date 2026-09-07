"""Magic-number acceptance tests for the package summary header."""
import struct

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.constants import PACKAGE_FILE_TAG_SWAPPED
from uasset_read.exceptions import VersionError
from uasset_read.serializers.package_summary import _read_version_and_tag


def test_byte_swapped_tag_is_rejected():
    """Big-endian packages have no fixture evidence: reject explicitly, do not swap-parse."""
    archive = ByteArchive(struct.pack("<I", PACKAGE_FILE_TAG_SWAPPED))
    with pytest.raises(VersionError, match="big-endian"):
        _read_version_and_tag(archive)
