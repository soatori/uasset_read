from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.core import BatchResult, ParseError, list_formats, parse_batch, parse_single


pytestmark = pytest.mark.smoke


def test_list_formats_exposes_primary_outputs() -> None:
    formats = set(list_formats())
    assert {"json", "markdown"} <= formats


def test_parse_single_raises_on_failed_strict_parse() -> None:
    with patch("uasset_read.core.parse_uasset_with_linker") as parse:
        result = MagicMock()
        result.is_success = False
        result.errors = ["boom"]
        parse.return_value = result
        with pytest.raises(ParseError, match="Parse failed"):
            parse_single("broken.uasset", format="json", tolerant=False, max_file_size_mb=0)


def test_parse_single_rejects_large_file_before_parse(tmp_path: Path) -> None:
    asset = tmp_path / "large.uasset"
    asset.write_bytes(b"0" * 2048)
    with pytest.raises(ParseError, match="File too large"):
        parse_single(str(asset), max_file_size_mb=0.001)


def test_parse_batch_returns_batch_result(tmp_path: Path) -> None:
    asset = tmp_path / "asset.uasset"
    asset.write_bytes(b"dummy")
    with patch("uasset_read.core.parse_single", return_value='{"status": "success"}'):
        result = parse_batch(str(tmp_path), format="json")
    assert isinstance(result, BatchResult)
    assert result.total == 1
    assert len(result.success) == 1


def test_parse_batch_sanitizes_output_paths(tmp_path: Path) -> None:
    asset = tmp_path / "normal.uasset"
    asset.write_bytes(b"dummy")
    output_dir = tmp_path / "out"
    with patch("uasset_read.core.parse_single", return_value="ok"):
        result = parse_batch(str(tmp_path), format="../escape", output_dir=str(output_dir))
    output_path = Path(result.success[0]).resolve()
    assert output_path.parent == output_dir.resolve()
    assert output_path.name == "normal.escape"


def test_partial_status_has_diagnostic_reason():
    """partial/opaque 状态必须附带可追踪原因"""
    from uasset_read.models.properties import StructValue

    # 构造一个 opaque struct
    sv = StructValue(
        struct_type="TestStruct",
        fields={},
        raw_size=-1,
        parse_status="opaque",
        unsupported_reason="negative_struct_size:-1",
    )
    assert sv.parse_status == "opaque"
    assert sv.unsupported_reason != ""
    assert "negative_struct_size" in sv.unsupported_reason


def test_cli_single_file_delegates_to_parse_single() -> None:
    from uasset_read.cli import main

    with patch("uasset_read.cli.parse_single", return_value='{"ok": true}') as parse:
        with patch("pathlib.Path.is_file", return_value=True):
            with patch("sys.argv", ["uasset_read", "asset.uasset", "--json"]):
                with pytest.raises(SystemExit) as exc:
                    main()
    assert exc.value.code == 0
    parse.assert_called_once()


def test_serialization_control_flags_parsed():
    """SerializationControlExtensions 已知位应被结构化解析"""
    from uasset_read.serializers.property_tags import parse_ue511_ctrl_flags

    # 0x03 = has_array_index + serialize_control
    result = parse_ue511_ctrl_flags(0x03)
    assert result["has_array_index"] is True
    assert result["serialize_control"] is True
    assert result["has_extensions"] is False

    # 0x00 = 无扩展
    result = parse_ue511_ctrl_flags(0x00)
    assert all(v is False for v in result.values())

    # 0x3F = 所有已知位
    result = parse_ue511_ctrl_flags(0x3F)
    assert all(v is True for v in result.values())
