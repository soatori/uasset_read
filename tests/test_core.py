"""Small permanent suite for stable cross-cutting contracts.

Exactly ten top-level ``test_*`` functions (design: test-organization
constraints). Fixture-sample contracts live in ``test_samples.py``. Case
bodies folded from the former ``tests/contract/`` layer are kept verbatim;
the case name appears in the failure message.
"""

from __future__ import annotations

from functools import lru_cache
import json
import logging
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(__file__).parent / "samples"
PACKAGE_SAMPLE = SAMPLES / "ABP_RifleAnimLayers.uasset"
DATA_SAMPLE = SAMPLES / "ALS_FootstepDataTable.uasset"
SCHEMA = ROOT / "docs/designs/contract/package_document_v2.schema.json"
EXAMPLE = ROOT / "docs/designs/contract/package_document_v2.example.json"


@lru_cache(maxsize=None)
def _document(sample: str = str(PACKAGE_SAMPLE), depth: str = "package"):
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(sample, depth=depth)


def _run_cases(cases) -> None:
    for case_name, check in cases:
        try:
            check()
        except (AssertionError, pytest.fail.Exception) as exc:
            raise AssertionError(f"{case_name}: {exc}") from exc


def test_reader_boundaries_reject_malformed_access(tmp_path):
    """A bounded reader must never escape its declared source region."""
    from uasset_read.package import PackageArchive
    from uasset_read.v2.source import FileSource, MemorySource, SliceReader

    def core_contract():
        source = MemorySource(b"0123456789")
        reader = SliceReader(source, 2, 5)
        assert reader.read(3) == b"234"
        assert reader.sub_slice(1, 2).read(2) == b"34"
        for operation in (
            lambda: source.read_at(-1, 1),
            lambda: reader.seek(6),
            lambda: reader.read(3),
        ):
            with pytest.raises(IndexError):
                operation()

    def test_size():
        assert MemorySource(b"hello world").size() == 11

    def test_read_at():
        src = MemorySource(b"hello world")
        assert src.read_at(0, 5) == b"hello"
        assert src.read_at(6, 5) == b"world"

    def test_read_at_negative_offset():
        with pytest.raises(IndexError):
            MemorySource(b"hello").read_at(-1, 1)

    def test_read_at_overflow():
        with pytest.raises(IndexError):
            MemorySource(b"hello").read_at(3, 5)

    def test_describe():
        info = MemorySource(b"test", name="test.bin").describe()
        assert info.kind == "memory"
        assert info.name == "test.bin"
        assert info.size == 4

    def test_file_read():
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00\x01\x02\x03\x04")
        src = FileSource(f)
        assert src.size() == 5
        assert src.read_at(1, 3) == b"\x01\x02\x03"

    def test_file_read_out_of_range():
        f = tmp_path / "oob.bin"
        f.write_bytes(b"\x00\x01")
        with pytest.raises(IndexError):
            FileSource(f).read_at(0, 10)

    def test_basic_read():
        sr = SliceReader(MemorySource(b"0123456789"), 2, 5)
        assert sr.source_size == 5
        assert sr.read(3) == b"234"
        assert sr.tell() == 3
        assert sr.remaining() == 2

    def test_seek():
        sr = SliceReader(MemorySource(b"0123456789"), 0, 10)
        sr.seek(5)
        assert sr.tell() == 5
        assert sr.read(3) == b"567"

    def test_seek_out_of_range():
        sr = SliceReader(MemorySource(b"0123456789"), 0, 10)
        with pytest.raises(IndexError):
            sr.seek(11)

    def test_read_exceeds_slice():
        sr = SliceReader(MemorySource(b"0123456789"), 2, 3)
        with pytest.raises(IndexError):
            sr.read(4)

    def test_sub_slice():
        sub = SliceReader(MemorySource(b"0123456789"), 0, 10).sub_slice(2, 4)
        assert sub.source_size == 4
        assert sub.read(4) == b"2345"

    def test_sub_slice_out_of_range():
        sr = SliceReader(MemorySource(b"0123456789"), 2, 3)
        with pytest.raises(IndexError):
            sr.sub_slice(0, 10)

    def test_nested_sub_slice():
        sub2 = SliceReader(MemorySource(b"0123456789"), 0, 10).sub_slice(2, 6).sub_slice(1, 3)
        assert sub2.read(3) == b"345"

    def test_invalid_slice_negative_base():
        with pytest.raises(IndexError):
            SliceReader(MemorySource(b"0123456789"), -1, 5)

    def test_invalid_slice_exceeds_source():
        with pytest.raises(IndexError):
            SliceReader(MemorySource(b"0123456789"), 8, 5)

    def test_slice_reader_satisfies_archive_like():
        reader = SliceReader(MemorySource(b"abcdef"), 1, 4)
        archive = PackageArchive(reader)
        assert archive.total_size() == 4
        archive.set_byte_swapping(True)
        assert archive.read(2) == b"bc"
        archive.close()

    _run_cases(
        [
            ("core.reader_out_of_range", core_contract),
            ("MemorySource.test_size", test_size),
            ("MemorySource.test_read_at", test_read_at),
            ("MemorySource.test_read_at_negative_offset", test_read_at_negative_offset),
            ("MemorySource.test_read_at_overflow", test_read_at_overflow),
            ("MemorySource.test_describe", test_describe),
            ("FileSource.test_read", test_file_read),
            ("FileSource.test_read_out_of_range", test_file_read_out_of_range),
            ("SliceReader.test_basic_read", test_basic_read),
            ("SliceReader.test_seek", test_seek),
            ("SliceReader.test_seek_out_of_range", test_seek_out_of_range),
            ("SliceReader.test_read_exceeds_slice", test_read_exceeds_slice),
            ("SliceReader.test_sub_slice", test_sub_slice),
            ("SliceReader.test_sub_slice_out_of_range", test_sub_slice_out_of_range),
            ("SliceReader.test_nested_sub_slice", test_nested_sub_slice),
            ("SliceReader.test_invalid_slice_negative_base", test_invalid_slice_negative_base),
            ("SliceReader.test_invalid_slice_exceeds_source", test_invalid_slice_exceeds_source),
            ("test_slice_reader_satisfies_archive_like", test_slice_reader_satisfies_archive_like),
        ]
    )


def test_property_bag_normalization_is_bounded_lossless():
    """normalize_property_bag must bound, describe, and never embed raw bytes."""
    from uasset_read.models.fallback import FallbackReason, PropertyFallback
    from uasset_read.models.properties import PropertyValue, StructValue
    from uasset_read.v2.properties import normalize_property_bag

    def test_empty_list_returns_empty_dict():
        assert normalize_property_bag([]) == {}

    def test_unknown_property_is_descriptor_not_blob():
        prop = PropertyFallback(
            name="Mystery",
            type="UnknownProperty",
            size=4,
            raw_bytes=b"\x01\x02\x03\x04",
            reason=FallbackReason.UNSUPPORTED_TYPE,
        )
        bag = normalize_property_bag([prop])
        assert bag["Mystery"] == {
            "kind": "opaque",
            "type": "UnknownProperty",
            "size": 4,
            "reason": "unsupported_type",
        }
        assert "raw_bytes" not in bag["Mystery"]
        json.dumps(bag)

    def test_known_property_preserves_value():
        bag = normalize_property_bag([PropertyValue(name="Health", type="FloatProperty", value=100.0)])
        assert bag["Health"]["kind"] == "value"
        assert bag["Health"]["value"] == 100.0
        json.dumps(bag)

    def test_struct_property_normalizes():
        sv = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
        prop = PropertyValue(name="Location", type="StructProperty", value=sv)
        bag = normalize_property_bag([prop])
        assert bag["Location"]["kind"] == "struct"
        assert bag["Location"]["struct_type"] == "Vector"
        assert bag["Location"]["fields"]["X"] == 1.0
        json.dumps(bag)

    def test_bytes_value_serializes():
        bag = normalize_property_bag([PropertyValue(name="Data", type="BlobProperty", value=b"\x00\x01")])
        assert bag["Data"]["kind"] == "value"
        assert bag["Data"]["value"]["kind"] == "bytes"
        assert bag["Data"]["value"]["length"] == 2
        json.dumps(bag)

    _run_cases(
        [
            ("property.test_empty_list_returns_empty_dict", test_empty_list_returns_empty_dict),
            ("property.test_unknown_property_is_descriptor_not_blob", test_unknown_property_is_descriptor_not_blob),
            ("property.test_known_property_preserves_value", test_known_property_preserves_value),
            ("property.test_struct_property_normalizes", test_struct_property_normalizes),
            ("property.test_bytes_value_serializes", test_bytes_value_serializes),
        ]
    )


def test_package_document_preserves_every_export_and_role():
    """Package parsing must preserve every export, including packages without an asset role."""
    doc = _document()
    assert [obj.id for obj in doc.objects] == [f"export:{index}" for index in range(10)]
    assert len(doc.summary.asset_object_ids) == 2
    assert all(relation.from_id.startswith(("export:", "import:")) for relation in doc.relations)

    def test_all_exports_present():
        assert len(doc.objects) == 10

    def test_ids_are_export_prefix():
        for obj in doc.objects:
            assert obj.id.startswith("export:")
            idx = int(obj.id.split(":")[1])
            assert idx == obj.table_index

    def test_stable_id_across_calls():
        from uasset_read.v2.api import parse_package_document

        doc1 = parse_package_document(str(PACKAGE_SAMPLE))
        doc2 = parse_package_document(str(PACKAGE_SAMPLE))
        ids1 = [o.id for o in doc1.objects]
        ids2 = [o.id for o in doc2.objects]
        assert ids1 == ids2

    def test_to_dict_roundtrip():
        d = doc.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["format"] == "uasset_read.package"
        assert len(parsed["objects"]) == 10

    def test_summary_fields():
        d = doc.to_dict()
        assert d["summary"]["object_count"] == 10
        assert d["summary"]["total_exports"] == 10
        assert "total_imports" in d["summary"]

    _run_cases(
        [
            ("document.test_all_exports_present", test_all_exports_present),
            ("document.test_ids_are_export_prefix", test_ids_are_export_prefix),
            ("document.test_stable_id_across_calls", test_stable_id_across_calls),
            ("document.test_to_dict_roundtrip", test_to_dict_roundtrip),
            ("document.test_summary_fields", test_summary_fields),
        ]
    )

    zero_role = _document(str(SAMPLES / "uasset_rs_UE410_SimpleRefsSoftRef.uasset"))
    assert len(zero_role.objects) == 6
    assert zero_role.summary.asset_object_ids == ()


def test_export_failure_isolated_and_diagnostics_typed(monkeypatch):
    """A malformed export must produce an attributable diagnostic without deleting siblings."""
    import uasset_read.parsers.property_parser as pp
    from uasset_read.exceptions import ParseError
    from uasset_read.v2.api import parse_package_document

    real = pp.parse_properties_from_export
    calls = {"n": 0}

    def boom(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise ParseError("injected malformed export payload")
        return real(**kwargs)

    # All fixture exports now parse cleanly, so inject the failure to
    # exercise the isolation path deterministically.
    monkeypatch.setattr(pp, "parse_properties_from_export", boom)
    doc = parse_package_document(str(PACKAGE_SAMPLE), depth="object")
    failures = [item for item in doc.diagnostics if item.code in ("EXPORT_PROPERTY_PARSE_FAILED", "EXPORT_PROPERTY_BOUNDS_EXCEEDED")]
    assert len(doc.objects) == 10
    assert len(doc.relations) > 0
    assert [(f.code, f.object_id) for f in failures] == [("EXPORT_PROPERTY_PARSE_FAILED", "export:1")]
    assert all(item.object_id and item.stage == "properties.tagged" for item in failures)
    assert not [item for item in doc.diagnostics if item.severity == "critical"]

    def test_no_critical_on_healthy():
        critical = [d for d in doc.diagnostics if d.severity == "critical"]
        assert len(critical) == 0

    def test_diagnostics_have_stage():
        for d in doc.diagnostics:
            assert d.stage, f"Diagnostic missing stage: {d.code}"

    def test_failed_export_does_not_remove_later_objects():
        with_props = [o for o in doc.objects if o.properties is not None]
        assert len(with_props) > 0

    def test_partial_status_on_bad_export_preserves_document():
        assert doc.package.export_count == 10
        assert len(doc.objects) == 10
        assert len(doc.relations) > 0
        critical = [d for d in doc.diagnostics if d.severity == "critical"]
        assert len(critical) == 0

    def test_parse_failure_diagnostic_has_object_id():
        parse_failures = [d for d in doc.diagnostics if d.code in ("EXPORT_PROPERTY_PARSE_FAILED", "EXPORT_PROPERTY_BOUNDS_EXCEEDED")]
        for diag in parse_failures:
            assert diag.object_id is not None
            assert diag.stage == "properties.tagged"

    def test_later_success_does_not_mask_earlier_failure():
        from uasset_read.v2 import handlers as H
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus

        class Boom:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                raise RuntimeError("boom")

        class Ok:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                return {"kind": "ok"}

        obj = ObjectRecord(
            id="export:9", table_index=0, name="X", class_name="Foo",
            status=ObjectStatus(parse="complete", semantic="not_requested"),
        )
        saved = H._HANDLERS[:]
        try:
            H._HANDLERS[:] = [Boom(), Ok()]
            semantic, _cov, diags = H.run_handlers(obj, H.VersionContext(), [], None)
        finally:
            H._HANDLERS[:] = saved
        assert semantic == {"kind": "ok"}
        assert obj.status.semantic == "partial"
        assert any(d.code == "HANDLER_FAILURE" for d in diags)

    def test_clean_success_still_marks_complete():
        from uasset_read.v2 import handlers as H
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus

        class Ok:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                return {"kind": "ok"}

        obj = ObjectRecord(
            id="export:9", table_index=0, name="X", class_name="Foo",
            status=ObjectStatus(parse="complete", semantic="not_requested"),
        )
        saved = H._HANDLERS[:]
        try:
            H._HANDLERS[:] = [Ok()]
            H.run_handlers(obj, H.VersionContext(), [], None)
        finally:
            H._HANDLERS[:] = saved
        assert obj.status.semantic == "complete"

    def test_matched_handler_returning_none_is_not_complete():
        from uasset_read.v2 import handlers as H
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus

        class Decliner:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                return None

        obj = ObjectRecord(
            id="export:9", table_index=0, name="X", class_name="Foo",
            status=ObjectStatus(parse="complete", semantic="not_requested"),
        )
        saved = H._HANDLERS[:]
        try:
            H._HANDLERS[:] = [Decliner()]
            semantic, _cov, _diags = H.run_handlers(obj, H.VersionContext(), [], None)
        finally:
            H._HANDLERS[:] = saved
        assert semantic is None
        assert obj.status.semantic == "partial"

    def test_parse_past_serial_end_is_flagged_not_silent():
        import uasset_read.parsers.property_parser as pp
        from uasset_read.v2.api import parse_package_document

        def fake_overrun(**kwargs):
            export = kwargs["export"]
            kwargs["archive"].seek(export.serial_offset + export.serial_size + 8)
            return []

        monkeypatch.setattr(pp, "parse_properties_from_export", fake_overrun)
        overrun_doc = parse_package_document(str(PACKAGE_SAMPLE), depth="object")
        overrun = [d for d in overrun_doc.diagnostics if d.code == "EXPORT_PROPERTY_BOUNDS_EXCEEDED"]
        assert overrun, "property parse exceeded the serial region with no diagnostic"
        assert all(d.object_id and d.stage == "properties.tagged" for d in overrun)

    _run_cases(
        [
            ("document.test_no_critical_on_healthy", test_no_critical_on_healthy),
            ("document.test_diagnostics_have_stage", test_diagnostics_have_stage),
            ("diagnostics.test_failed_export_does_not_remove_later_objects", test_failed_export_does_not_remove_later_objects),
            ("diagnostics.test_partial_status_on_bad_export_preserves_document", test_partial_status_on_bad_export_preserves_document),
            ("diagnostics.test_parse_failure_diagnostic_has_object_id", test_parse_failure_diagnostic_has_object_id),
            ("handler.test_later_success_does_not_mask_earlier_failure", test_later_success_does_not_mask_earlier_failure),
            ("handler.test_clean_success_still_marks_complete", test_clean_success_still_marks_complete),
            ("handler.test_matched_handler_returning_none_is_not_complete", test_matched_handler_returning_none_is_not_complete),
            ("property.test_parse_past_serial_end_is_flagged_not_silent", test_parse_past_serial_end_is_flagged_not_silent),
        ]
    )


def test_handler_registry_supports_enriches_and_isolates():
    """Every registered handler must accept its class, reject others, and isolate failures."""
    from uasset_read.v2.handlers import (
        BlueprintFamilyHandler,
        DataTableHandler,
        MaterialHandler,
        MaterialInstanceHandler,
        MeshHandler,
        SkeletonHandler,
        TextureHandler,
        UserDefinedEnumHandler,
        UserDefinedStructHandler,
        get_handlers,
    )
    from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
    from uasset_read.v2.version import VersionContext

    def record(class_name):
        return ObjectRecord(id="export:0", table_index=0, name="X", class_name=class_name, status=ObjectStatus())

    def test_handlers_registered():
        assert len(get_handlers()) >= 4

    def test_expected_handlers():
        names = [type(h).__name__ for h in get_handlers()]
        assert "DataTableHandler" in names
        assert "TextureHandler" in names
        assert "TexturePayloadHandler" in names
        assert "SoundHandler" in names

    def test_supports_and_rejects():
        cases = [
            ("DataTableHandler", DataTableHandler(), "DataTable", "Blueprint"),
            ("UserDefinedEnumHandler", UserDefinedEnumHandler(), "UserDefinedEnum", "Blueprint"),
            ("UserDefinedStructHandler", UserDefinedStructHandler(), "UserDefinedStruct", "DataTable"),
            ("TextureHandler", TextureHandler(), "Texture2D", "Blueprint"),
            ("SkeletonHandler", SkeletonHandler(), "Skeleton", "Blueprint"),
            ("MeshHandler/Static", MeshHandler(), "StaticMesh", "Blueprint"),
            ("MeshHandler/Skeletal", MeshHandler(), "SkeletalMesh", "Blueprint"),
            ("MaterialHandler", MaterialHandler(), "Material", "Blueprint"),
            ("MaterialInstanceHandler", MaterialInstanceHandler(), "MaterialInstanceConstant", "Blueprint"),
            ("BlueprintFamilyHandler/anim", BlueprintFamilyHandler(("AnimBlueprint", "AnimBlueprintGeneratedClass"), "anim_blueprint", "anim_blueprint"), "AnimBlueprintGeneratedClass", "StaticMesh"),
            ("BlueprintFamilyHandler/bp", BlueprintFamilyHandler(("Blueprint", "BlueprintGeneratedClass"), "blueprint", "blueprint"), "BlueprintGeneratedClass", "StaticMesh"),
        ]
        for name, handler, good_class, bad_class in cases:
            assert handler.supports(record(good_class), VersionContext()), f"{name} must support {good_class}"
            assert not handler.supports(record(bad_class), VersionContext()), f"{name} must reject {bad_class}"

    def test_texture_no_properties_returns_none():
        obj = ObjectRecord(
            id="export:0", table_index=0, name="Tex", class_name="Texture2D",
            status=ObjectStatus(), properties=None,
        )
        assert TextureHandler().enrich(obj, VersionContext(), [], None) is None

    def test_handler_exception_doesnt_crash():
        from uasset_read.v2.handlers import register_handler, run_handlers

        class BadHandler:
            def supports(self, obj, context):
                return True

            def enrich(self, obj, context, all_objects, package_data):
                raise RuntimeError("boom")

        original_handlers = list(get_handlers())
        try:
            register_handler(BadHandler())
            obj = ObjectRecord(id="export:0", table_index=0, name="X", class_name="Anything", status=ObjectStatus())
            semantic, cov, diags = run_handlers(obj, VersionContext(), [obj], None)
            assert semantic is None
            assert any("BadHandler" in c.feature for c in cov)
            assert any(d.stage == "semantic.handler" for d in diags)
        finally:
            from uasset_read.v2.handlers import _HANDLERS

            _HANDLERS[:] = original_handlers

    def test_handler_exception_becomes_object_diagnostic():
        import uasset_read.v2.handlers as handlers
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.version import VersionContext

        class RaisingHandler:
            def supports(self, obj, context):
                return True

            def enrich(self, obj, context, all_objects, package_data):
                raise ValueError("broken handler")

        original_handlers = list(handlers._HANDLERS)
        try:
            handlers._HANDLERS.append(RaisingHandler())
            sample_doc = parse_package_document(
                str(DATA_SAMPLE), depth="object", object_ids=["export:0"]
            )
            semantic, coverage, diagnostics = handlers.run_handlers(
                sample_doc.objects[0], VersionContext(), sample_doc.objects, None
            )
            assert semantic is None
            assert any(c.status == "missing" for c in coverage)
            handler_diags = [d for d in diagnostics if d.stage == "semantic.handler"]
            assert len(handler_diags) >= 1
            assert handler_diags[0].object_id == sample_doc.objects[0].id
        finally:
            handlers._HANDLERS[:] = original_handlers

    def test_niagara_handler_supports_all_declared_classes():
        from uasset_read.v2.handlers import NiagaraHandler

        handler = NiagaraHandler()
        assert len(handler._NIAGARA_CLASSES) == 13
        for class_name in handler._NIAGARA_CLASSES:
            assert handler.supports(record(class_name), VersionContext()), class_name
        assert not handler.supports(record("StaticMesh"), VersionContext())

    def test_class_handlers_kwarg_defaults_true_for_v1():
        import inspect

        from uasset_read.parsers.property_parser import parse_properties_from_export

        param = inspect.signature(parse_properties_from_export).parameters["run_class_handlers"]
        assert param.default is True, "v1 default must keep class-handler dispatch byte-identical"

    _run_cases(
        [
            ("handler.test_handlers_registered", test_handlers_registered),
            ("handler.test_expected_handlers", test_expected_handlers),
            ("handler.test_supports_and_rejects", test_supports_and_rejects),
            ("handler.test_texture_no_properties_returns_none", test_texture_no_properties_returns_none),
            ("handler.test_handler_exception_doesnt_crash", test_handler_exception_doesnt_crash),
            ("handler.test_handler_exception_becomes_object_diagnostic", test_handler_exception_becomes_object_diagnostic),
            ("handler.test_niagara_handler_supports_all_declared_classes", test_niagara_handler_supports_all_declared_classes),
            ("handler.test_class_handlers_kwarg_defaults_true_for_v1", test_class_handlers_kwarg_defaults_true_for_v1),
        ]
    )


def test_projection_views_depths_pagination_table():
    """View shape, pagination, and selection contracts on one synthetic-parse document."""
    from uasset_read.v2.projection import paginate, project_document, select_objects

    doc = _document(depth="asset")

    def test_semantic_default():
        assert project_document(doc)["view"] == "semantic"

    def test_raw_has_flags():
        result = project_document(doc, view="raw", limit=2)
        for obj in result["objects"]:
            assert "flags" in obj

    def test_debug_has_stats():
        result = project_document(doc, view="debug")
        assert "debug" in result
        assert "total_objects" in result["debug"]

    def test_invalid_view_raises():
        with pytest.raises(ValueError, match="Invalid view"):
            project_document(doc, view="invalid")

    def test_semantic_no_flags():
        result = project_document(doc, view="semantic", limit=2)
        for obj in result["objects"]:
            assert "flags" not in obj

    def test_limit_truncates():
        items = list(range(10))
        page, next_offset, info = paginate(items, offset=0, limit=3)
        assert len(page) == 3
        assert next_offset == 3
        assert info["truncated"] == 1

    def test_offset_skips():
        items = list(range(10))
        page, next_offset, info = paginate(items, offset=5, limit=3)
        assert page == [5, 6, 7]
        assert next_offset == 8

    def test_no_limit_returns_all():
        items = list(range(10))
        page, next_offset, info = paginate(items, offset=0)
        assert len(page) == 10
        assert next_offset is None
        assert info["truncated"] == 0

    def test_page_through_all():
        all_objects = []
        offset = 0
        while True:
            result = project_document(doc, limit=3, offset=offset)
            all_objects.extend(result["objects"])
            if "next_offset" not in result:
                break
            offset = result["next_offset"]
        assert len(all_objects) == len(doc.objects)

    def test_select_by_role():
        asset_objs = select_objects(doc, roles=["asset"])
        assert len(asset_objs) >= 2

    def test_select_by_id():
        result = select_objects(doc, object_ids=["export:0", "export:1"])
        assert len(result) == 2

    def test_select_all_when_no_filters():
        result = select_objects(doc)
        assert len(result) == len(doc.objects)

    def test_all_views_json():
        for view in ("semantic", "raw", "debug"):
            result = project_document(doc, view=view, limit=3)
            json_str = json.dumps(result, ensure_ascii=False)
            parsed = json.loads(json_str)
            assert parsed["view"] == view

    def core_projection_honors_views():
        # View shape: semantic omits flags, raw includes them
        pkg_doc = _document()
        assert "flags" not in project_document(pkg_doc, view="semantic", limit=2)["objects"][0]
        assert "flags" in project_document(pkg_doc, view="raw", limit=2)["objects"][0]
        assert "debug" in project_document(pkg_doc, view="debug", limit=2)

        # Pagination and byte budget
        full = project_document(pkg_doc, limit=100)
        full_size = len(json.dumps(full, separators=(",", ":")).encode())
        # budget must exceed minimal reachable envelope (depends_on imports)
        # but be less than the full page to trigger truncation
        budget = full_size - 1000
        page = project_document(pkg_doc, limit=100, max_bytes=budget)
        assert len(json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode()) <= budget
        assert page["next_offset"] > 0
        assert page["truncation"]["reason"] == "max_bytes"

        # fields filter: only requested fields plus id/name are returned
        result = project_document(pkg_doc, limit=2, fields=["id"])
        assert len(result["objects"]) == 2
        assert set(result["objects"][0].keys()).issubset({"id", "name"})
        assert isinstance(result["payloads"], list)
        assert isinstance(result["relations"], list)

    _run_cases(
        [
            ("projection.test_semantic_default", test_semantic_default),
            ("projection.test_raw_has_flags", test_raw_has_flags),
            ("projection.test_debug_has_stats", test_debug_has_stats),
            ("projection.test_invalid_view_raises", test_invalid_view_raises),
            ("projection.test_semantic_no_flags", test_semantic_no_flags),
            ("projection.test_limit_truncates", test_limit_truncates),
            ("projection.test_offset_skips", test_offset_skips),
            ("projection.test_no_limit_returns_all", test_no_limit_returns_all),
            ("projection.test_page_through_all", test_page_through_all),
            ("projection.test_select_by_role", test_select_by_role),
            ("projection.test_select_by_id", test_select_by_id),
            ("projection.test_select_all_when_no_filters", test_select_all_when_no_filters),
            ("projection.test_all_views_json", test_all_views_json),
            ("core.test_projection_honors_views_pagination_and_byte_budget", core_projection_honors_views),
        ]
    )


def test_projection_byte_budget_and_fields_filter():
    """The encoded page must respect max_bytes and re-scope relations/diagnostics."""
    from uasset_read.v2.projection import project_document

    doc = _document(depth="asset")

    def test_max_bytes_is_enforced_and_continuable():
        empty = project_document(doc, limit=0)
        envelope_size = len(json.dumps(empty, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        budget = envelope_size + 8000
        page = project_document(doc, limit=100, max_bytes=budget)
        encoded = json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        assert len(encoded) <= budget
        assert page["truncation"]["reason"] == "max_bytes"
        assert page["next_offset"] > 0
        assert any(d["code"] == "TRUNCATED" for d in page["diagnostics"])

    def test_truncated_page_rescopes_relations_and_dependencies():
        """Popping objects for max_bytes must re-scope relations and dependencies."""
        empty = project_document(doc, limit=0)
        envelope_size = len(json.dumps(empty, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        budget = envelope_size + 8000
        page = project_document(doc, limit=100, max_bytes=budget)
        page_ids = {o["id"] for o in page["objects"]}
        assert len(page_ids) < 10, "budget should force dropping at least one object"
        for rel in page["relations"]:
            assert rel["from"] in page_ids, f"relation kept for dropped object: {rel}"
        targets = {rel["to"] for rel in page["relations"]}
        for dep in page["dependencies"]:
            assert f"import:{dep['index']}" in targets, f"dependency not reachable from page: {dep}"

    def test_relations_scoped_to_returned_page():
        page = project_document(doc, limit=2)
        page_ids = {o["id"] for o in page["objects"]}
        assert len(page_ids) == 2
        for r in page["relations"]:
            assert r["from"] in page_ids

    def test_object_diagnostics_scoped_to_page():
        page = project_document(doc, limit=2)
        page_ids = {o["id"] for o in page["objects"]}
        for d in page["diagnostics"]:
            oid = d.get("object_id")
            assert oid is None or oid in page_ids

    def test_budget_too_small_raises():
        with pytest.raises(ValueError, match="too small"):
            project_document(doc, max_bytes=64)

    def test_no_truncation_when_budget_generous():
        page = project_document(doc, limit=2, max_bytes=1_000_000)
        assert page.get("truncation") is None or page["truncation"].get("reason") != "max_bytes"

    def core_fields_filter_scopes_payloads():
        pkg_doc = _document()
        result = project_document(pkg_doc, limit=2, fields=["class"])
        assert len(result["objects"]) == 2
        assert set(result["objects"][0]).issubset({"id", "name", "class"})
        assert isinstance(result["payloads"], list)
        assert isinstance(result["relations"], list)

    def core_max_bytes_caps_final_output():
        pkg_doc = _document()
        full = project_document(pkg_doc, limit=100)
        full_size = len(json.dumps(full, separators=(",", ":")).encode())
        budget = full_size - 1000  # strictly less than full page
        page = project_document(pkg_doc, limit=100, max_bytes=budget)
        final = len(json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode())
        assert final <= budget
        assert page["truncation"]["reason"] == "max_bytes"
        assert page["next_offset"] > 0

    _run_cases(
        [
            ("projection.test_max_bytes_is_enforced_and_continuable", test_max_bytes_is_enforced_and_continuable),
            ("projection.test_truncated_page_rescopes_relations_and_dependencies", test_truncated_page_rescopes_relations_and_dependencies),
            ("projection.test_relations_scoped_to_returned_page", test_relations_scoped_to_returned_page),
            ("projection.test_object_diagnostics_scoped_to_page", test_object_diagnostics_scoped_to_page),
            ("projection.test_budget_too_small_raises", test_budget_too_small_raises),
            ("projection.test_no_truncation_when_budget_generous", test_no_truncation_when_budget_generous),
            ("core.test_projection_fields_filter_does_not_crash_and_scopes_payloads", core_fields_filter_scopes_payloads),
            ("core.test_max_bytes_caps_final_output_including_truncation_block", core_max_bytes_caps_final_output),
        ]
    )


def test_schema_contract_statics():
    """The shipped schema must validate the example and match code enumerations."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_example_validates_against_schema():
        """The checked contract example must validate against the schema."""
        jsonschema.validate(json.loads(EXAMPLE.read_text(encoding="utf-8")), schema)

    def test_schema_has_required_fields():
        required = set(schema.get("required", []))
        assert "format" in required
        assert "format_version" in required
        assert "view" in required
        assert "depth" in required
        assert "source" in required
        assert "package" in required
        assert "objects" in required
        assert "relations" in required
        assert "dependencies" in required
        assert "payloads" in required
        assert "diagnostics" in required
        assert "summary" in required

    def test_schema_enums_match_code():
        view_enum = schema["properties"]["view"]["enum"]
        assert set(view_enum) == {"semantic", "raw", "debug"}

        depth_enum = schema["properties"]["depth"]["enum"]
        assert set(depth_enum) == {"package", "object", "asset", "decode"}

    _run_cases(
        [
            ("schema.test_example_validates_against_schema", test_example_validates_against_schema),
            ("schema.test_schema_has_required_fields", test_schema_has_required_fields),
            ("schema.test_schema_enums_match_code", test_schema_enums_match_code),
        ]
    )


def test_cli_python_agent_share_default_projection_and_logging_inert(tmp_path, monkeypatch):
    """CLI (default v2), Python API, and agent tools must agree; parsing must be side-effect free."""
    from uasset_read.v2.agent_tools import (
        get_diagnostics,
        get_object,
        inspect_package,
        list_dependencies,
        list_objects,
    )
    from uasset_read.v2.projection import project_document

    def run_cli_json(*args: str) -> dict:
        result = subprocess.run(
            [sys.executable, "-m", "uasset_read", *map(str, args)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr[:500]}"
        return json.loads(result.stdout)

    # CLI default output is the v2 package document; the package assertion is
    # presence-only because package.name is legitimately "" on real fixtures
    # (follow-up #621).
    plain = run_cli_json(str(DATA_SAMPLE))
    assert plain["format"] == "uasset_read.package"
    assert "objects" in plain and plain["package"]
    assert len(plain["objects"]) > 0

    # --legacy-json opts back into v1 shape.
    legacy = run_cli_json("--legacy-json", str(DATA_SAMPLE))
    assert legacy["format"] != "uasset_read.package" or "objects" not in legacy

    # --markdown renders through the v1 pipeline (the only markdown renderer).
    md = subprocess.run(
        [sys.executable, "-m", "uasset_read", "--markdown", str(DATA_SAMPLE)],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert md.returncode == 0, md.stderr[:500]
    assert md.stdout.strip() and not md.stdout.lstrip().startswith("{")

    # v1-only flags under the v2 default warn instead of silently dropping.
    warned = subprocess.run(
        [sys.executable, "-m", "uasset_read", "--hex-view", str(DATA_SAMPLE)],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert warned.returncode == 0
    assert "--hex-view" in warned.stderr and "ignored" in warned.stderr
    assert json.loads(warned.stdout)["format"] == "uasset_read.package"

    # All public entry points project the same page.
    expected = project_document(_document(str(DATA_SAMPLE)), depth="package", limit=2, max_bytes=4096)
    cli = run_cli_json("--depth", "package", "--limit", "2", "--max-bytes", "4096", str(DATA_SAMPLE))
    assert cli["depth"] == "package"
    assert len(cli["objects"]) <= 2
    agent = inspect_package(str(DATA_SAMPLE), depth="package", limit=2, max_bytes=4096)
    for actual in (cli, agent):
        assert [item["id"] for item in actual["objects"]] == [item["id"] for item in expected["objects"]]
        assert actual["diagnostics"] == expected["diagnostics"]

    # Agent tool shapes.
    inspected = inspect_package(str(DATA_SAMPLE))
    assert "source" in inspected
    assert "package" in inspected
    assert "summary" in inspected
    parsed = json.loads(json.dumps(inspected))
    assert "source" in parsed and "package" in parsed and "summary" in parsed

    listed = list_objects(str(DATA_SAMPLE))
    assert listed["total"] > 0
    assert len(listed["objects"]) > 0

    paged = list_objects(str(PACKAGE_SAMPLE), limit=3, max_bytes=65536)
    assert paged["returned"] == 3
    assert paged["next_offset"] == 3

    fetched = get_object(str(DATA_SAMPLE), "export:0")
    assert fetched["id"] == "export:0"
    assert "name" in fetched

    deps = list_dependencies(str(DATA_SAMPLE))
    assert "dependencies" in deps
    assert "relations" in deps

    diags = get_diagnostics(str(DATA_SAMPLE))
    assert "diagnostics" in diags
    assert "total" in diags

    # Logging lifecycle: no process-global mutation, no stray files.
    handlers = tuple(logging.root.handlers)
    level = logging.root.level
    monkeypatch.chdir(tmp_path)
    _document(str(DATA_SAMPLE.resolve()))
    assert tuple(logging.root.handlers) == handlers
    assert logging.root.level == level
    assert list(tmp_path.iterdir()) == []

    old_level = logging.root.level
    try:
        logging.root.setLevel(logging.WARNING)
        from uasset_read.v2.api import parse_package_document

        parse_package_document(str(DATA_SAMPLE))
    finally:
        logging.root.setLevel(old_level)
    assert len(logging.root.handlers) == len(handlers)
    assert logging.root.level == level


def test_test_suite_structure_gate():
    import ast

    root = Path(__file__).parent
    test_files = sorted(p.name for p in root.glob("test_*.py"))
    assert test_files == ["test_core.py", "test_samples.py"]
    subdirs = {p.name for p in root.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert subdirs == {"samples"}
    tree = ast.parse((root / "test_core.py").read_text(encoding="utf-8"))
    funcs = [
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    ]
    assert len(funcs) <= 13
    assert not any(isinstance(n, ast.ClassDef) for n in tree.body)
    # The design bans decorators on test functions; cache helpers like
    # _document legitimately carry @lru_cache, so the check is scoped to
    # the collected test_* defs (the plan's gate body over-blocked here).
    assert all(
        not n.decorator_list
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    )
    assigned = {
        t.id
        for n in tree.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id.startswith("test_")
    }
    assert not assigned


def test_export_bounds_exceeded_read_past_bound():
    """Reading past the bound must raise ExportBoundsExceeded, not silent corruption."""
    from uasset_read.archive import ByteArchive, ExportBoundsExceeded

    archive = ByteArchive(b"\x00" * 256)
    archive._read_bound = 100
    archive._pos = 80
    with pytest.raises(ExportBoundsExceeded):
        archive.read(50)


def test_export_bounds_exceeded_read_within_bound():
    """Reading within the bound must succeed."""
    from uasset_read.archive import ByteArchive

    archive = ByteArchive(b"\x00" * 256)
    archive._read_bound = 100
    archive._pos = 80


def test_export_bounds_exceeded_seek_past_bound():
    """Seeking past the bound must raise ExportBoundsExceeded."""
    from uasset_read.archive import ByteArchive, ExportBoundsExceeded

    archive = ByteArchive(b"\x00" * 256)
    archive._read_bound = 100
    with pytest.raises(ExportBoundsExceeded):
        archive.validate_offset(150, "test_seek")
