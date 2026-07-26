"""Parse every tracked local sample through the public tolerant API."""

from pathlib import Path

import pytest

from uasset_read import parse_uasset_with_linker


SAMPLE_ROOT = Path(__file__).resolve().parent / "samples"
SAMPLE_FILES = tuple(sorted(SAMPLE_ROOT.glob("*.uasset")))
if not SAMPLE_FILES:
    raise RuntimeError(f"No .uasset samples found in {SAMPLE_ROOT}")


@pytest.mark.samples
@pytest.mark.parametrize("sample_path", SAMPLE_FILES, ids=lambda path: path.name)
def test_all_tracked_samples_parse(sample_path: Path):
    result = parse_uasset_with_linker(str(sample_path), tolerant=True)

    assert result.is_success, f"{sample_path.name}: {result.errors}"
    assert not result.errors, f"{sample_path.name}: {result.errors}"
    assert result.linker is not None, sample_path.name
    assert result.name_map, sample_path.name
    assert result.export_map, sample_path.name
