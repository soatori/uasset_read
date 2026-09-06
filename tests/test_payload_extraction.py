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


def test_extract_payload_main_read_failure():
    """Test that extract_payload returns error when main file doesn't exist."""
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
    assert "Read failed" in result.error
    assert result.data == b""


def test_extract_payload_with_missing_sidecar():
    """Test that extract_payload returns error when sidecar file doesn't exist."""
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
    assert result.extracted is False
    assert "Read failed" in result.error


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


def test_extract_payload_from_uexp():
    """Test extracting payload from .uexp sidecar."""
    fixture_dir = Path(__file__).parent / "samples"
    main_path = fixture_dir / "T_ParserBulk.uasset"
    uexp_path = fixture_dir / "T_ParserBulk.uexp"

    if not main_path.exists():
        pytest.skip("T_ParserBulk.uasset fixture not found")

    # T_ParserBulk.uexp is 22308 bytes
    descriptor = PayloadDescriptor(
        id="payload:(export:0)",
        owner="export:0",
        kind="bulk_data",
        source_region="uexp",
        offset=0,
        stored_size=22308,
        status="available",
    )

    result = extract_payload_bytes(
        descriptor,
        main_path=main_path,
        sidecar_paths={"uexp": uexp_path},
    )

    assert result.extracted is True
    assert result.error is None
    assert len(result.data) == 22308
    assert result.descriptor is descriptor


def test_extract_payload_from_uexp_with_offset():
    """Test extracting payload from .uexp with offset."""
    fixture_dir = Path(__file__).parent / "samples"
    main_path = fixture_dir / "T_ParserBulk.uasset"
    uexp_path = fixture_dir / "T_ParserBulk.uexp"

    if not main_path.exists():
        pytest.skip("T_ParserBulk.uasset fixture not found")

    # Read first 100 bytes from offset 100
    descriptor = PayloadDescriptor(
        id="payload:(export:0)",
        owner="export:0",
        kind="bulk_data",
        source_region="uexp",
        offset=100,
        stored_size=100,
        status="available",
    )

    result = extract_payload_bytes(
        descriptor,
        main_path=main_path,
        sidecar_paths={"uexp": uexp_path},
    )

    assert result.extracted is True
    assert result.error is None
    assert len(result.data) == 100


def test_extract_payload_short_read():
    """Test extraction when stored_size exceeds file size."""
    fixture_dir = Path(__file__).parent / "samples"
    main_path = fixture_dir / "T_ParserBulk.uasset"
    uexp_path = fixture_dir / "T_ParserBulk.uexp"

    if not main_path.exists():
        pytest.skip("T_ParserBulk.uasset fixture not found")

    # Request more bytes than available
    descriptor = PayloadDescriptor(
        id="payload:(export:0)",
        owner="export:0",
        kind="bulk_data",
        source_region="uexp",
        offset=0,
        stored_size=100000,  # uexp is only 22308 bytes
        status="available",
    )

    result = extract_payload_bytes(
        descriptor,
        main_path=main_path,
        sidecar_paths={"uexp": uexp_path},
    )

    assert result.extracted is False
    assert "Short read" in result.error
    assert len(result.data) == 22308  # Got what was available


def test_extract_payload_missing_sidecar_returns_deferred():
    """Test that missing sidecar returns DEFERRED."""
    descriptor = PayloadDescriptor(
        id="payload:(export:0)",
        owner="export:0",
        kind="bulk_data",
        source_region="ubulk",
        offset=0,
        stored_size=1024,
        status="available",
    )

    # No sidecar_paths provided
    result = extract_payload_bytes(
        descriptor,
        main_path=Path("nonexistent.uasset"),
    )

    assert result.extracted is False
    assert result.error == PAYLOAD_EXTRACTION_DEFERRED
    assert result.data == b""


def test_sidecar_discovery():
    """Test that PackageBundle provides sidecar path properties."""
    from uasset_read.package import open_package_bundle

    fixture_dir = Path(__file__).parent / "samples"
    main_path = fixture_dir / "T_ParserBulk.uasset"

    if not main_path.exists():
        pytest.skip("T_ParserBulk.uasset fixture not found")

    bundle = open_package_bundle(str(main_path))

    # T_ParserBulk has .uexp and .ubulk sidecars
    assert bundle.uexp_path is not None
    assert bundle.uexp_path.exists()
    assert bundle.uexp_path.suffix == ".uexp"

    assert bundle.ubulk_path is not None
    assert bundle.ubulk_path.exists()
    assert bundle.ubulk_path.suffix == ".ubulk"

    # T_ParserBulk does NOT have .uptnl sidecar
    assert bundle.uptnl_path is None

    # main_path_obj should be a Path
    assert isinstance(bundle.main_path_obj, Path)
    assert bundle.main_path_obj == Path(bundle.main_path)

    # Verify Path caching: same object returned on repeated access
    assert bundle.uexp_path is bundle.uexp_path
    assert bundle.ubulk_path is bundle.ubulk_path
    assert bundle.uptnl_path is bundle.uptnl_path
    assert bundle.main_path_obj is bundle.main_path_obj


def test_agent_tool_extract_payload():
    """Test agent tool extract_payload with real fixture."""
    import base64

    from uasset_read.agent_tools import extract_payload

    fixture_dir = Path(__file__).parent / "samples"
    main_path = fixture_dir / "T_ParserBulk.uasset"

    if not main_path.exists():
        pytest.skip("T_ParserBulk.uasset not found")

    # Call the agent tool with export_index
    result = extract_payload(
        file_path=str(main_path),
        payload_id="payload:(export:0)",
        export_index=0,
    )

    # Should not return DEFERRED anymore - should extract real bytes
    assert result.get("error") != PAYLOAD_EXTRACTION_DEFERRED
    assert "data" in result
    assert "size" in result
    assert result["size"] > 0

    # Verify the data is valid base64
    data = base64.b64decode(result["data"])
    assert len(data) == result["size"]


def test_agent_tool_extract_payload_auto_index():
    """Test agent tool extract_payload derives export_index from payload_id."""
    import base64

    from uasset_read.agent_tools import extract_payload

    fixture_dir = Path(__file__).parent / "samples"
    main_path = fixture_dir / "T_ParserBulk.uasset"

    if not main_path.exists():
        pytest.skip("T_ParserBulk.uasset not found")

    # Call without export_index - should derive from payload_id
    result = extract_payload(
        file_path=str(main_path),
        payload_id="payload:(export:0)",
    )

    # Should not return DEFERRED
    assert result.get("error") != PAYLOAD_EXTRACTION_DEFERRED
    assert "data" in result
    assert result["size"] > 0


def test_agent_tool_extract_payload_nonexistent_package():
    """Test agent tool extract_payload with nonexistent package."""
    from uasset_read.agent_tools import extract_payload

    result = extract_payload(
        file_path="nonexistent.uasset",
        payload_id="payload:(export:0)",
    )

    assert "error" in result
    assert result["code"] == "PACKAGE_NOT_FOUND"
    assert result["recoverable"] is False


def test_agent_tool_extract_payload_invalid_payload_id():
    """Test agent tool extract_payload with invalid payload_id format."""
    from uasset_read.agent_tools import extract_payload

    fixture_dir = Path(__file__).parent / "samples"
    main_path = fixture_dir / "T_ParserBulk.uasset"

    if not main_path.exists():
        pytest.skip("T_ParserBulk.uasset not found")

    # Invalid payload_id format - cannot derive export_index
    result = extract_payload(
        file_path=str(main_path),
        payload_id="invalid_format",
    )

    # Should return DEFERRED since we can't determine export index
    assert result.get("code") == PAYLOAD_EXTRACTION_DEFERRED
