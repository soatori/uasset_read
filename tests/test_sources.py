import pytest

from uasset_read.exceptions import ParseError
from uasset_read.sources import CompositeSource, MemorySource


def test_composite_source_maps_sidecar_ranges(tmp_path):
    main = tmp_path / "A.uasset"
    sidecar = tmp_path / "A.uexp"
    main.write_bytes(b"HEAD")
    sidecar.write_bytes(b"PAYLOAD")
    source = CompositeSource.from_package(main)
    assert source.read_at(0, 4) == b"HEAD"
    assert source.read_at(4, 7) == b"PAYLOAD"
    assert source.map_range(2, 5) == [("A.uasset", 2, 2), ("A.uexp", 0, 3)]


def test_source_rejects_out_of_bounds_reads():
    source = MemorySource(b"abc")
    with pytest.raises(ParseError):
        source.read_at(2, 2)


def test_memory_source_rejects_negative_offset():
    source = MemorySource(b"abc")
    with pytest.raises(ParseError):
        source.read_at(-1, 1)
