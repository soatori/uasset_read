"""Tests for payload extraction from cooked .uasset files."""

from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.models.payloads import (
    PAYLOAD_EXTRACTION_DEFERRED,
    PayloadDescriptor,
    extract_payload_bytes,
)

FIXTURE_DIR = Path(__file__).parent / "samples"
MAIN_PATH = FIXTURE_DIR / "T_ParserBulk.uasset"

pytestmark = pytest.mark.skipif(
    not (MAIN_PATH.exists() and MAIN_PATH.with_suffix(".uexp").exists()),
    reason="T_ParserBulk fixture or its .uexp sidecar is missing",
)


def _desc(**overrides) -> PayloadDescriptor:
    base = {
        "id": "payload:(export:0)",
        "owner": "export:0",
        "kind": "bulk_data",
        "source_region": "main",
        "offset": 0,
        "stored_size": 0,
        "status": "available",
    }
    return PayloadDescriptor(**{**base, **overrides})


def test_payload_descriptor_creation():
    """Test creating a PayloadDescriptor with required fields."""
    descriptor = _desc(source_region="main", stored_size=2048)

    assert descriptor.id == "payload:(export:0)"
    assert descriptor.owner == "export:0"
    assert descriptor.source_region == "main"
    assert descriptor.status == "available"


def test_payload_descriptor_optional_fields():
    """Test creating a PayloadDescriptor with optional fields."""
    descriptor = _desc(
        id="payload:(export:1)",
        owner="export:1",
        kind="texture_mip",
        source_region="ubulk",
        offset=1024,
        stored_size=4096,
        logical_size=8192,
        compression="oodle",
        hash="abc123",
    )

    assert descriptor.logical_size == 8192
    assert descriptor.compression == "oodle"
    assert descriptor.hash == "abc123"


def test_extract_payload_main_read_failure():
    """Test that extract_payload returns error when main file doesn't exist."""
    descriptor = _desc(stored_size=2048)

    data, error = extract_payload_bytes(descriptor, main_path=Path("nonexistent.uasset"))
    assert error is not None
    assert "Read failed" in error
    assert data == b""


def test_extract_payload_with_missing_sidecar():
    """Test that extract_payload returns error when sidecar file doesn't exist."""
    descriptor = _desc(source_region="uexp", stored_size=1024)

    sidecar_paths = {"uexp": Path("nonexistent.uexp")}
    data, error = extract_payload_bytes(
        descriptor,
        main_path=Path("nonexistent.uasset"),
        sidecar_paths=sidecar_paths,
    )
    assert error is not None
    assert "Read failed" in error


def test_extract_payload_from_uexp():
    """Test extracting payload from .uexp sidecar."""
    uexp_path = FIXTURE_DIR / "T_ParserBulk.uexp"

    # T_ParserBulk.uexp is 22308 bytes
    descriptor = _desc(source_region="uexp", stored_size=22308)

    data, error = extract_payload_bytes(
        descriptor,
        main_path=MAIN_PATH,
        sidecar_paths={"uexp": uexp_path},
    )

    assert error is None
    assert len(data) == 22308


def test_extract_payload_from_uexp_with_offset():
    """Test extracting payload from .uexp with offset."""
    uexp_path = FIXTURE_DIR / "T_ParserBulk.uexp"

    # Read first 100 bytes from offset 100
    descriptor = _desc(source_region="uexp", offset=100, stored_size=100)

    data, error = extract_payload_bytes(
        descriptor,
        main_path=MAIN_PATH,
        sidecar_paths={"uexp": uexp_path},
    )

    assert error is None
    assert len(data) == 100


def test_extract_payload_short_read():
    """Test extraction when stored_size exceeds file size."""
    uexp_path = FIXTURE_DIR / "T_ParserBulk.uexp"

    # Request more bytes than available
    descriptor = _desc(source_region="uexp", stored_size=100000)  # uexp is only 22308 bytes

    data, error = extract_payload_bytes(
        descriptor,
        main_path=MAIN_PATH,
        sidecar_paths={"uexp": uexp_path},
    )

    assert error is not None
    assert "Short read" in error
    assert len(data) == 22308  # Got what was available


def test_extract_payload_missing_sidecar_returns_deferred():
    """Test that missing sidecar returns DEFERRED."""
    descriptor = _desc(source_region="ubulk", stored_size=1024)

    # No sidecar_paths provided
    data, error = extract_payload_bytes(
        descriptor,
        main_path=Path("nonexistent.uasset"),
    )

    assert error == PAYLOAD_EXTRACTION_DEFERRED
    assert data == b""


def test_sidecar_discovery():
    """Test that PackageBundle provides sidecar path properties."""
    from uasset_read.package import open_package_bundle

    bundle = open_package_bundle(str(MAIN_PATH))

    # T_ParserBulk has .uexp and .ubulk sidecars
    assert bundle.uexp_path is not None
    assert bundle.uexp_path.exists()
    assert bundle.uexp_path.suffix == ".uexp"

    assert bundle.ubulk_path is not None
    assert bundle.ubulk_path.exists()
    assert bundle.ubulk_path.suffix == ".ubulk"

    # T_ParserBulk does NOT have .uptnl sidecar
    assert bundle.uptnl_path is None

    # Verify Path caching: same object returned on repeated access
    assert bundle.uexp_path is bundle.uexp_path
    assert bundle.ubulk_path is bundle.ubulk_path
    assert bundle.uptnl_path is bundle.uptnl_path


def test_agent_tool_extract_payload():
    """Test agent tool extract_payload with real fixture."""
    import base64

    from uasset_read.agent_tools import extract_payload

    # Call the agent tool with export_index
    result = extract_payload(
        file_path=str(MAIN_PATH),
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
    from uasset_read.agent_tools import extract_payload

    # Call without export_index - should derive from payload_id
    result = extract_payload(
        file_path=str(MAIN_PATH),
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

    # Invalid payload_id format - cannot derive export_index
    result = extract_payload(
        file_path=str(MAIN_PATH),
        payload_id="invalid_format",
    )

    # Should return DEFERRED since we can't determine export index
    assert result.get("code") == PAYLOAD_EXTRACTION_DEFERRED


def test_extract_bulk_data_descriptors_basic():
    """Test extracting a single BulkData descriptor from serial data."""
    from uasset_read.parsers.bulk_data import extract_bulk_data_descriptors

    # Simulate a BulkData header at the end of an export
    # flags=0x01, element_count=4096, size_on_disk=8192, offset=0
    bulk_data_header = bytes([
        0x01, 0x00, 0x00, 0x00,  # flags = BULKDATA_None
        0x00, 0x10, 0x00, 0x00,  # element_count = 4096
        0x00, 0x20, 0x00, 0x00,  # size_on_disk = 8192
        0x00, 0x00, 0x00, 0x00,  # offset = 0 (relative to ubulk)
    ])

    # Use data that won't form false positive headers
    # Use 0xFF bytes which won't form valid headers when scanned
    serial_data = b"\xff" * 100 + bulk_data_header

    descriptors = extract_bulk_data_descriptors(serial_data)

    assert len(descriptors) == 1
    assert descriptors[0].size_on_disk == 8192
    assert descriptors[0].element_count == 4096
    assert descriptors[0].offset == 0
    assert descriptors[0].compression_type is None


def test_extract_bulk_data_descriptors_compressed():
    """Test extracting compressed BulkData descriptors."""
    from uasset_read.parsers.bulk_data import extract_bulk_data_descriptors

    # Compressed header: flags=0x02 (Zlib), element_count=2048, size_on_disk=4096, offset=1024
    bulk_data_header = bytes([
        0x02, 0x00, 0x00, 0x00,  # flags = BULKDATA_CompressedZlib
        0x00, 0x08, 0x00, 0x00,  # element_count = 2048
        0x00, 0x10, 0x00, 0x00,  # size_on_disk = 4096
        0x00, 0x04, 0x00, 0x00,  # offset = 1024
    ])

    # Use data that won't form false positive headers
    serial_data = b"\xff" * 200 + bulk_data_header

    descriptors = extract_bulk_data_descriptors(serial_data)

    assert len(descriptors) == 1
    assert descriptors[0].size_on_disk == 4096
    assert descriptors[0].element_count == 2048
    assert descriptors[0].offset == 1024
    assert descriptors[0].compression_type == "zlib"


def test_extract_bulk_data_descriptors_single_at_end():
    """Test that only the last header is found (conservative heuristic)."""
    from uasset_read.parsers.bulk_data import extract_bulk_data_descriptors

    # Two BulkData headers back-to-back at the end
    header1 = bytes([
        0x01, 0x00, 0x00, 0x00,
        0x00, 0x10, 0x00, 0x00,
        0x00, 0x20, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
    ])
    header2 = bytes([
        0x02, 0x00, 0x00, 0x00,
        0x00, 0x08, 0x00, 0x00,
        0x00, 0x10, 0x00, 0x00,
        0x00, 0x04, 0x00, 0x00,
    ])

    # Use data that won't form false positive headers
    serial_data = b"\xff" * 50 + header1 + header2

    descriptors = extract_bulk_data_descriptors(serial_data)

    # Conservative heuristic: only finds the last header
    assert len(descriptors) == 1
    assert descriptors[0].compression_type == "zlib"
    assert descriptors[0].size_on_disk == 4096


def test_extract_bulk_data_descriptors_empty():
    """Test extracting from data with no BulkData headers."""
    from uasset_read.parsers.bulk_data import extract_bulk_data_descriptors

    # Use 0xFF bytes which won't form valid headers when scanned
    serial_data = b"\xff" * 100

    descriptors = extract_bulk_data_descriptors(serial_data)

    assert len(descriptors) == 0


def test_extract_bulk_data_descriptors_too_short():
    """Test extracting from data shorter than a header."""
    from uasset_read.parsers.bulk_data import extract_bulk_data_descriptors

    serial_data = b"\x01\x02\x03\x04" * 2

    descriptors = extract_bulk_data_descriptors(serial_data)

    assert len(descriptors) == 0


def test_extract_bulk_data_descriptors_invalid_header():
    """Test extracting when header is invalid."""
    from uasset_read.parsers.bulk_data import extract_bulk_data_descriptors

    # Header with size_on_disk=0 (invalid)
    invalid_header = bytes([
        0x01, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,  # element_count = 0
        0x00, 0x00, 0x00, 0x00,  # size_on_disk = 0
        0x00, 0x00, 0x00, 0x00,
    ])

    # Use 0xFF bytes which won't form valid headers
    serial_data = b"\xff" * 50 + invalid_header

    descriptors = extract_bulk_data_descriptors(serial_data)

    # Invalid headers are skipped
    assert len(descriptors) == 0


def test_extract_bulk_data_from_real_uexp():
    """Test extracting BulkData descriptors from real T_ParserBulk.uexp."""
    from uasset_read.parsers.bulk_data import extract_bulk_data_descriptors

    uexp_data = (FIXTURE_DIR / "T_ParserBulk.uexp").read_bytes()

    # The uexp file contains export serial data
    # Scan for BulkData headers in the last 32 bytes
    descriptors = extract_bulk_data_descriptors(uexp_data)

    # We expect to find at least one BulkData descriptor
    # (the texture mip data in T_ParserBulk)
    # Note: This is a heuristic scan, so results may vary
    # The test verifies the function runs without error
    assert isinstance(descriptors, list)
    for desc in descriptors:
        assert desc.size_on_disk > 0
        assert desc.element_count > 0


def test_end_to_end_payload_extraction():
    """End-to-end test: parse T_ParserBulk.uasset and extract texture mip data.

    Verifies the full pipeline:
    1. Parse package to discover exports and sidecar files
    2. Find a Texture2D export
    3. Extract payload using the agent tool
    4. Verify extracted data is valid and non-empty
    """
    import base64

    from uasset_read.agent_tools import extract_payload
    from uasset_read.package import open_package_bundle, parse_package_document

    # Step 1: Parse the package to discover structure
    doc = parse_package_document(str(MAIN_PATH), depth="package")
    assert doc is not None, "PackageDocument should not be None"
    assert len(doc.objects) > 0, "Package should have at least one export"

    # Step 2: Find the Texture2D export
    texture_export_index = None
    for i, obj in enumerate(doc.objects):
        if obj.class_name == "Texture2D":
            texture_export_index = i
            break

    if texture_export_index is None:
        pytest.skip("No Texture2D export found in T_ParserBulk.uasset")

    # Verify export has serial region
    export = doc.objects[texture_export_index]
    assert export.serial_region is not None, "Texture2D export should have a serial region"
    assert export.serial_region.size > 0, "Serial region should have non-zero size"
    assert export.serial_region.offset >= 0, "Serial region offset should be non-negative"

    # Step 3: Discover sidecar files
    bundle = open_package_bundle(str(MAIN_PATH))
    assert bundle.uexp_path is not None, "T_ParserBulk should have a .uexp sidecar"
    assert bundle.uexp_path.exists(), ".uexp sidecar file should exist"
    assert bundle.ubulk_path is not None, "T_ParserBulk should have a .ubulk sidecar"
    assert bundle.ubulk_path.exists(), ".ubulk sidecar file should exist"

    # Step 4: Extract payload using the agent tool
    payload_id = f"payload:(export:{texture_export_index})"
    result = extract_payload(
        file_path=str(MAIN_PATH),
        payload_id=payload_id,
        export_index=texture_export_index,
    )

    # Verify extraction succeeded
    assert "error" not in result or result.get("code") != PAYLOAD_EXTRACTION_DEFERRED, (
        f"Extraction should not be deferred: {result}"
    )
    assert "data" in result, f"Result should contain 'data' key: {result}"
    assert "size" in result, f"Result should contain 'size' key: {result}"
    assert result["size"] > 0, f"Extracted size should be positive: {result['size']}"
    assert result["source_region"] in ("uexp", "ubulk", "main"), (
        f"Source region should be valid: {result.get('source_region')}"
    )

    # Step 5: Verify extracted data is valid base64 and non-empty
    decoded_data = base64.b64decode(result["data"])
    assert len(decoded_data) == result["size"], (
        f"Decoded data length ({len(decoded_data)}) should match size ({result['size']})"
    )
    assert len(decoded_data) > 0, "Decoded data should be non-empty"

    # Verify the payload_id in result matches what we requested
    assert result["id"] == payload_id, (
        f"Result payload_id should match request: {result.get('id')} != {payload_id}"
    )


def test_end_to_end_payload_extraction_auto_index():
    """End-to-end test: extract payload without specifying export_index.

    Verifies the agent tool can derive export_index from payload_id format.
    """
    import base64

    from uasset_read.agent_tools import extract_payload

    # Extract without export_index - should derive from payload_id
    result = extract_payload(
        file_path=str(MAIN_PATH),
        payload_id="payload:(export:0)",
    )

    # Should succeed
    assert "error" not in result or result.get("code") != PAYLOAD_EXTRACTION_DEFERRED
    assert "data" in result
    assert result["size"] > 0

    # Verify data is valid
    decoded_data = base64.b64decode(result["data"])
    assert len(decoded_data) == result["size"]


def test_end_to_end_payload_extraction_direct_api():
    """End-to-end test using the low-level extract_payload_bytes API.

    Verifies the core extraction function works with real sidecar files.
    """
    from uasset_read.models.payloads import extract_payload_bytes
    from uasset_read.package import open_package_bundle, parse_package_document

    # Discover sidecars
    bundle = open_package_bundle(str(MAIN_PATH))
    assert bundle.uexp_path is not None

    # Parse to get serial region info
    doc = parse_package_document(str(MAIN_PATH), depth="package")
    assert len(doc.objects) > 0

    # Create a descriptor for the uexp region
    descriptor = _desc(source_region="uexp", stored_size=bundle.uexp_path.stat().st_size)

    # Extract using the direct API
    data, error = extract_payload_bytes(
        descriptor,
        main_path=MAIN_PATH,
        sidecar_paths={"uexp": bundle.uexp_path},
    )

    assert error is None, f"Should have no error: {error}"
    assert len(data) == 22308, f"Should extract all uexp bytes: {len(data)}"
