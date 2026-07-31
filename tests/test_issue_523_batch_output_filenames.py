"""Regression coverage for #523 batch output filename replacement."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from uasset_read import core


@pytest.mark.parametrize(
    ("format_name", "extension"),
    [("json", ".json"), ("markdown", ".md")],
)
def test_parse_batch_replaces_input_suffix_in_success_paths_and_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    format_name: str,
    extension: str,
) -> None:
    """Batch output replaces .uasset/.umap rather than appending to them."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    input_names = ("Actor.uasset", "ExampleMap.umap")
    for name in input_names:
        (input_dir / name).write_bytes(b"fixture")

    monkeypatch.setattr(
        "uasset_read.memory_safety.get_memory_stats",
        lambda: SimpleNamespace(usage_percent=0.0),
    )

    def fake_parse_and_render(file_path: str, **_kwargs):
        return f"rendered:{Path(file_path).name}", SimpleNamespace(
            status="success",
            export_map=[],
        )

    monkeypatch.setattr(core, "_parse_and_render", fake_parse_and_render)

    result = core.parse_batch(
        str(input_dir),
        format=format_name,
        output_dir=str(output_dir),
        isolate_assets=False,
        log_enabled=False,
    )

    expected_names = [f"Actor{extension}", f"ExampleMap{extension}"]
    expected_paths = [str(output_dir / name) for name in expected_names]
    assert result.total == 2
    assert result.success == expected_paths
    assert result.partial == []
    assert result.partial_reasons == {}
    assert result.skipped == []
    assert result.failed == []

    for input_name, expected_name in zip(input_names, expected_names):
        assert (output_dir / expected_name).read_text(encoding="utf-8") == (
            f"rendered:{input_name}"
        )
        assert not (output_dir / f"{input_name}{extension}").exists()
