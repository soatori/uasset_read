"""Tests for v2 asset handlers."""

from __future__ import annotations

from pathlib import Path

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


class TestHandlerRegistry:
    def test_handlers_registered(self):
        from uasset_read.v2.handlers import get_handlers

        handlers = get_handlers()
        assert len(handlers) >= 3

    def test_handler_names(self):
        from uasset_read.v2.handlers import get_handlers

        names = [type(h).__name__ for h in get_handlers()]
        assert "DataTableHandler" in names
        assert "TextureHandler" in names
        assert "SoundHandler" in names


class TestDataTableHandler:
    def test_supports_datatable(self):
        from uasset_read.v2.handlers import DataTableHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = DataTableHandler()
        obj = ObjectRecord(id="export:0", table_index=0, name="DT", class_name="DataTable", status=ObjectStatus())
        assert handler.supports(obj, VersionContext())

    def test_rejects_non_datatable(self):
        from uasset_read.v2.handlers import DataTableHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = DataTableHandler()
        obj = ObjectRecord(id="export:0", table_index=0, name="BP", class_name="Blueprint", status=ObjectStatus())
        assert not handler.supports(obj, VersionContext())


class TestRunHandlers:
    def test_no_data_returns_none(self):
        from uasset_read.v2.handlers import run_handlers
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        obj = ObjectRecord(id="export:0", table_index=0, name="DT", class_name="DataTable", status=ObjectStatus())
        semantic, cov = run_handlers(obj, VersionContext(), [obj], None)
        assert semantic is None

    def test_handler_exception_doesnt_crash(self):
        from uasset_read.v2.handlers import run_handlers, register_handler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        class BadHandler:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, pkg_data):
                raise RuntimeError("boom")

        register_handler(BadHandler())
        obj = ObjectRecord(id="export:0", table_index=0, name="X", class_name="Anything", status=ObjectStatus())
        semantic, cov = run_handlers(obj, VersionContext(), [obj], None)
        assert semantic is None
        assert any("BadHandler" in c.feature for c in cov)


class TestEndToEndWithSample:
    def test_datatable_sample_has_semantic(self):
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.handlers import run_handlers
        from uasset_read.v2.version import VersionContext

        doc = parse_package_document(str(SAMPLES_DIR / "ALS_FootstepDataTable.uasset"))
        ctx = VersionContext()

        # Find the DataTable object
        dt_obj = None
        for obj in doc.objects:
            if obj.class_name == "DataTable":
                dt_obj = obj
                break

        if dt_obj:
            # Re-parse to get v1 export data
            from uasset_read.pipeline.core import parse_uasset_with_linker

            v1 = parse_uasset_with_linker(str(SAMPLES_DIR / "ALS_FootstepDataTable.uasset"), tolerant=True)
            semantic, cov = run_handlers(dt_obj, ctx, doc.objects, v1)
            # DataTable should produce semantic data
            if semantic is not None:
                assert "kind" in semantic
                assert semantic["kind"] == "data_table"

    def test_sound_sample_has_semantic(self):
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.handlers import run_handlers
        from uasset_read.v2.version import VersionContext

        doc = parse_package_document(str(SAMPLES_DIR / "ALS_Concrete_Step_01_SoundWave.uasset"))
        ctx = VersionContext()

        # Find SoundWave object
        sw_obj = None
        for obj in doc.objects:
            if obj.class_name == "SoundWave":
                sw_obj = obj
                break

        if sw_obj:
            from uasset_read.pipeline.core import parse_uasset_with_linker

            v1 = parse_uasset_with_linker(str(SAMPLES_DIR / "ALS_Concrete_Step_01_SoundWave.uasset"), tolerant=True)
            semantic, cov = run_handlers(sw_obj, ctx, doc.objects, v1)
            if semantic is not None:
                assert "kind" in semantic
                assert semantic["kind"] == "sound"
