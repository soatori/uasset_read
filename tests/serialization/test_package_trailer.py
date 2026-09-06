"""Tests for PackageTrailer constants and parsing."""
import pytest
from uasset_read.constants import (
    PACKAGE_TRAILER_HEADER_TAG,
    PACKAGE_TRAILER_FOOTER_TAG,
    PACKAGE_FILE_TAG,
    UE5_PAYLOAD_TOC,
    UE5_DATA_RESOURCES,
)


def test_header_tag_value():
    assert PACKAGE_TRAILER_HEADER_TAG == 0xD1C43B2E80A5F697


def test_footer_tag_value():
    assert PACKAGE_TRAILER_FOOTER_TAG == 0x29BFCA045138DE76


def test_payload_toc_version():
    assert UE5_PAYLOAD_TOC == 1002


def test_data_resources_version():
    assert UE5_DATA_RESOURCES == 1009
