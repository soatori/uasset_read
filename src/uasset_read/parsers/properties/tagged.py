"""Bounded tagged property stream reader — sole public tagged entry."""

from __future__ import annotations

from typing import Any

from uasset_read.archive import ByteArchive
from uasset_read.models.byte_ranges import ByteRegion, opaque_region, region_from_source
from uasset_read.models.diagnostics import Diagnostic
from uasset_read.models.properties import PropertyBag, PropertyEntry, PropertyValue
from uasset_read.parsers.properties import PropertyInput, PropertyReadResult


class TaggedPropertyReader:
    """Iterate PropertyTags until Name is None; never read past the export slice."""

    def read(self, input: PropertyInput) -> PropertyReadResult:
        end = input.start + input.size
        if input.size <= 0:
            empty = region_from_source(input.source, input.start, 0, status="decoded")
            return PropertyReadResult(
                values=PropertyBag(),
                consumed=0,
                regions=[empty],
                diagnostics=[],
                status="complete",
            )

        try:
            package_bytes = input.source.read_at(0, input.source.size() or 0)
        except Exception as exc:
            diag = Diagnostic(
                severity="error",
                code="TAGGED_SOURCE_UNREADABLE",
                message=str(exc),
                stage="properties.tagged",
                object_id=input.object_id,
                offset=input.start,
                size=input.size,
                effect="parse_failure",
                reason="unexpected",
            )
            region = opaque_region(input.start, input.size, "source_unreadable")
            return PropertyReadResult(
                values=PropertyBag(),
                consumed=0,
                regions=[region],
                diagnostics=[diag],
                status="failed",
            )

        # Reconstruct package-level context so FName indices resolve.
        try:
            from uasset_read.serializers.package_summary import (
                read_name_table,
                read_package_summary,
            )

            header = ByteArchive(package_bytes, name="<property-input>", tolerant=True)
            summary, _ = read_package_summary(header)
            name_map = read_name_table(ByteArchive(package_bytes, name="<names>", tolerant=True), summary)
            export_map, import_map = _load_tables(package_bytes, summary, name_map)
        except Exception as exc:
            diag = Diagnostic(
                severity="warning",
                code="TAGGED_CONTEXT_UNAVAILABLE",
                message=str(exc),
                stage="properties.tagged",
                object_id=input.object_id,
                offset=input.start,
                size=input.size,
                effect="semantic_loss",
                reason="unexpected",
            )
            region = opaque_region(input.start, input.size, "tagged_context_unavailable")
            return PropertyReadResult(
                values=PropertyBag(),
                consumed=0,
                regions=[region],
                diagnostics=[diag],
                status="unavailable",
            )

        window = ByteArchive(package_bytes[input.start : end], name=input.object_id)
        window._name_map = name_map
        window._file_version_ue4 = summary.file_version_ue4
        window._file_version_ue5 = summary.file_version_ue5
        window._tolerant = True

        from uasset_read.serializers.property_tags import read_property_tag
        from uasset_read.parsers.property_parser import parse_property_value

        bag = PropertyBag()
        regions: list[ByteRegion] = []
        diagnostics: list[Diagnostic] = []
        consumed = 0
        status: str = "complete"

        while window.tell() + 4 <= input.size:
            tag_start = window.tell()
            try:
                tag = read_property_tag(window, name_map, tolerant=True)
            except Exception as exc:
                remaining = input.size - tag_start
                if remaining > 0:
                    regions.append(
                        opaque_region(
                            input.start + tag_start,
                            remaining,
                            "tag_read_failed",
                        )
                    )
                    consumed = input.size
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="PROPERTY_TAG_READ_FAILED",
                        message=str(exc),
                        stage="properties.tagged",
                        object_id=input.object_id,
                        offset=input.start + tag_start,
                        size=remaining,
                        effect="semantic_loss",
                        reason="recovered_corruption",
                    )
                )
                status = "partial"
                break

            if tag.name == "None":
                regions.append(
                    region_from_source(
                        input.source,
                        input.start + tag_start,
                        window.tell() - tag_start,
                        status="decoded",
                        feature="terminator",
                    )
                )
                consumed = window.tell()
                break

            value_start = window.tell()
            try:
                value = parse_property_value(
                    tag,
                    window,
                    name_map,
                    export_map,
                    summary,
                    depth=0,
                    tolerant=True,
                )
            except Exception as exc:
                size = max(tag.size, 0)
                window.seek(min(value_start + size, input.size))
                value = None
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="PROPERTY_VALUE_READ_FAILED",
                        message=str(exc),
                        stage="properties.tagged",
                        object_id=input.object_id,
                        offset=input.start + value_start,
                        size=size,
                        effect="semantic_loss",
                        reason="recovered_corruption",
                    )
                )
                status = "partial"

            # Never run past the export slice.
            if window.tell() > input.size:
                window.seek(input.size)
                status = "partial"

            tag_region = region_from_source(
                input.source,
                input.start + tag_start,
                value_start - tag_start,
                status="decoded",
                feature="property_tag",
            )
            value_region = region_from_source(
                input.source,
                input.start + value_start,
                window.tell() - value_start,
                status="decoded" if value is not None else "opaque",
                feature="property_value",
                reason=None if value is not None else "value_read_failed",
            )
            regions.extend([tag_region, value_region])
            if isinstance(value, PropertyValue):
                bag.entries.append(
                    PropertyEntry(
                        name=value.name,
                        type_name=value.type,
                        value=value.value,
                        array_index=value.array_index,
                        tag_region=tag_region,
                        value_region=value_region,
                    )
                )
            elif value is not None:
                bag.entries.append(
                    PropertyEntry(
                        name=tag.name,
                        type_name=tag.type,
                        value=value,
                        array_index=tag.array_index,
                        tag_region=tag_region,
                        value_region=value_region,
                    )
                )
            consumed = window.tell()
        else:
            # Hit the bound without a None terminator.
            if consumed < input.size:
                regions.append(
                    opaque_region(
                        input.start + consumed,
                        input.size - consumed,
                        "tag_stream_unterminated",
                    )
                )
                consumed = input.size
            status = "partial"

        if not regions:
            regions.append(
                region_from_source(input.source, input.start, input.size, status="decoded")
            )
            consumed = input.size

        return PropertyReadResult(
            values=bag,
            consumed=consumed,
            regions=regions,
            diagnostics=diagnostics,
            status=status,  # type: ignore[arg-type]
        )


def _load_tables(package_bytes: bytes, summary: Any, name_map: list[str]):
    from uasset_read.serializers.object_resources import read_export_map, read_import_map

    ar = ByteArchive(package_bytes, name="<tables>", tolerant=True)
    ar._name_map = name_map
    ar.seek(int(summary.import_offset))
    import_map = read_import_map(ar, summary, name_map)
    ar.seek(int(summary.export_offset))
    export_map = read_export_map(ar, summary, name_map)
    return export_map, import_map
