"""Handler contract — DataTable, Texture, Sound real samples and handler failure isolation."""

from __future__ import annotations

from pathlib import Path


SAMPLES_DIR = Path(__file__).parent / "samples"


class TestHandlerRegistry:
    def test_handlers_registered(self):
        from uasset_read.v2.handlers import get_handlers
        handlers = get_handlers()
        assert len(handlers) >= 3

    def test_expected_handlers(self):
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


class TestHandlerFailureIsolation:
    def test_handler_exception_doesnt_crash(self):
        from uasset_read.v2.handlers import run_handlers, register_handler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        class BadHandler:
            def supports(self, obj, context):
                return True
            def enrich(self, obj, context, all_objects, package_data):
                raise RuntimeError("boom")

        register_handler(BadHandler())
        obj = ObjectRecord(id="export:0", table_index=0, name="X", class_name="Anything", status=ObjectStatus())
        semantic, cov = run_handlers(obj, VersionContext(), [obj], None)
        assert semantic is None
        assert any("BadHandler" in c.feature for c in cov)


class TestRealSamples:
    def test_datatable_sample(self):
        from uasset_read.v2.api import parse_package_document
        doc = parse_package_document(str(SAMPLES_DIR / "ALS_FootstepDataTable.uasset"))
        dt_objs = [o for o in doc.objects if o.class_name == "DataTable"]
        assert len(dt_objs) >= 1

    def test_texture_sample(self):
        from uasset_read.v2.api import parse_package_document
        doc = parse_package_document(str(SAMPLES_DIR / "FirstPerson_T_GridChecker_A.uasset"))
        tex_objs = [o for o in doc.objects if o.class_name == "Texture2D"]
        assert len(tex_objs) >= 1

    def test_sound_sample(self):
        from uasset_read.v2.api import parse_package_document
        doc = parse_package_document(str(SAMPLES_DIR / "ALS_Concrete_Step_01_SoundWave.uasset"))
        sw_objs = [o for o in doc.objects if o.class_name == "SoundWave"]
        assert len(sw_objs) >= 1