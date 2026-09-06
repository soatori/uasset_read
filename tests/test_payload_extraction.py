"""Tests for payload extraction from cooked .uasset files."""

from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.models.payloads import (
    PAYLOAD_EXTRACTION_DEFERRED,
    PayloadDescriptor,
    PayloadExtraction,
    extract_payload_bytes,
)


def test_payload_descriptor_creation():
    """Test creating a PayloadDescriptor with required fields."""
    descriptor = PayloadDescriptor(
        id="payload:(export:0)",
        owner="export:0",
        kind="bulk_data",
        source_region="main",
        offset=0,
        stored_size=2048,
        status="available",
    )

    assert descriptor.id == "payload:(export:0)"
    assert descriptor.owner == "export:0"
    assert descriptor.source_region == "main"
    assert descriptor.status == "available"


def test_payload_descriptor_optional_fields():
    """Test creating a PayloadDescriptor with optional fields."""
    descriptor = PayloadDescriptor(
        id="payload:(export:1)",
        owner="export:1",
        kind="texture_mip",
        source_region="ubulk",
        offset=1024,
        stored_size=4096,
        status="available",
        logical_size=8192,
        compression="oodle",
        hash="abc123",
    )

    assert descriptor.logical_size == 8192
    assert descriptor.compression == "oodle"
    assert descriptor.hash == "abc123"


def test_extract_payload_deferred():
    """Test that extract_payload returns DEFERRED when no sidecar exists."""
    descriptor = PayloadDescriptor(
        id="payload:(export:0)",
        owner="export:0",
        kind="bulk_data",
        source_region="main",
        offset=0,
        stored_size=2048,
        status="available",
    )

    result = extract_payload_bytes(descriptor, main_path=Path("nonexistent.uasset"))
    assert result.extracted is False
    assert result.error == PAYLOAD_EXTRACTION_DEFERRED
    assert result.data == b""


def test_extract_payload_with_sidecar_paths():
    """Test that extract_payload still returns DEFERRED even with sidecar paths."""
    descriptor = PayloadDescriptor(
        id="payload:(export:0)",
        owner="export:0",
        kind="bulk_data",
        source_region="uexp",
        offset=0,
        stored_size=1024,
        status="available",
    )

    sidecar_paths = {"uexp": Path("nonexistent.uexp")}
    result = extract_payload_bytes(
        descriptor,
        main_path=Path("nonexistent.uasset"),
        sidecar_paths=sidecar_paths,
    )
    assert result.error == PAYLOAD_EXTRACTION_DEFERRED


def test_payload_extraction_is_dataclass():
    """Test that PayloadExtraction is a proper dataclass."""
    descriptor = PayloadDescriptor(
        id="payload:(export:0)",
        owner="export:0",
        kind="other",
        source_region="main",
        offset=0,
        stored_size=0,
        status="missing",
    )
    extraction = PayloadExtraction(descriptor=descriptor, data=b"test", extracted=True)
    assert extraction.data == b"test"
    assert extraction.extracted is True
    assert extraction.error is None
