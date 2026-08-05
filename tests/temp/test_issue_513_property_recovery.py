from __future__ import annotations

from uasset_read.models.fallback import FallbackReason, PropertyFallback
from uasset_read.models.properties import PropertyTag
from uasset_read.parsers import property_parser
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex


class _Archive:
    _file_size = 64

    def __init__(self) -> None:
        self.position = 0
        self.seek_history: list[int] = []

    def tell(self) -> int:
        return self.position

    def seek(self, position: int) -> None:
        self.position = position
        self.seek_history.append(position)


def _export() -> ObjectExport:
    return ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="CorruptedExport",
        object_flags=0,
        serial_size=64,
        serial_offset=0,
    )


def _size_exceeded_tag() -> PropertyTag:
    return PropertyTag(
        name="BrokenProperty",
        type="StructProperty",
        size=128,
        tag_start_offset=0,
        size_exceeded=True,
    )


def test_size_exceeded_recovery_failure_stops_property_loop_as_partial(monkeypatch) -> None:
    archive = _Archive()
    export = _export()
    reads = 0

    def read_tag(*_args, **_kwargs):
        nonlocal reads
        reads += 1
        if reads > 1:
            raise AssertionError("failed recovery must not retry the same property tag")
        archive.seek(20)
        return _size_exceeded_tag()

    monkeypatch.setattr(property_parser, "read_property_tag", read_tag)
    monkeypatch.setattr(property_parser, "_try_recover_property_tag", lambda *_args, **_kwargs: False)

    properties = property_parser._read_property_loop(
        export, archive, summary=object(), name_map=[], export_map=[], import_map=None,
        linker=None, mappings=None, property_end=64, tolerant=True,
    )

    assert reads == 1
    assert export.parse_status == "partial"
    assert len(properties) == 1
    assert isinstance(properties[0].value, PropertyFallback)
    assert properties[0].value.reason is FallbackReason.SIZE_EXCEEDED


def test_size_exceeded_recovery_that_advances_continues_to_terminator(monkeypatch) -> None:
    archive = _Archive()
    export = _export()
    tags = iter((_size_exceeded_tag(), PropertyTag(name="None", type="", size=0)))
    reads = 0

    def read_tag(*_args, **_kwargs):
        nonlocal reads
        reads += 1
        if reads == 1:
            archive.seek(20)
        return next(tags)

    def recover(*_args, **_kwargs):
        archive.seek(32)
        return True

    monkeypatch.setattr(property_parser, "read_property_tag", read_tag)
    monkeypatch.setattr(property_parser, "_try_recover_property_tag", recover)

    properties = property_parser._read_property_loop(
        export, archive, summary=object(), name_map=[], export_map=[], import_map=None,
        linker=None, mappings=None, property_end=64, tolerant=True,
    )

    assert reads == 2
    assert archive.seek_history[-1] == 32
    assert len(properties) == 1
    assert properties[0].value.reason is FallbackReason.SIZE_EXCEEDED
