"""Handler contract — DataTable, Texture, Sound real samples and handler failure isolation."""

from __future__ import annotations

from pathlib import Path


SAMPLES_DIR = Path(__file__).parent / "samples"


class TestHandlerRegistry:
    def test_handlers_registered(self):
        from uasset_read.v2.handlers import get_handlers

        handlers = get_handlers()
        assert len(handlers) >= 4

    def test_expected_handlers(self):
        from uasset_read.v2.handlers import get_handlers

        names = [type(h).__name__ for h in get_handlers()]
        assert "DataTableHandler" in names
        assert "TextureHandler" in names
        assert "TexturePayloadHandler" in names
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


class TestUserDefinedEnumHandler:
    def test_supports(self):
        from uasset_read.v2.handlers import UserDefinedEnumHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = UserDefinedEnumHandler()
        obj = ObjectRecord(
            id="export:1", table_index=1, name="Enum_PanelType",
            class_name="UserDefinedEnum", status=ObjectStatus(),
        )
        assert handler.supports(obj, VersionContext())

    def test_rejects_non_enum(self):
        from uasset_read.v2.handlers import UserDefinedEnumHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = UserDefinedEnumHandler()
        obj = ObjectRecord(
            id="export:0", table_index=0, name="BP_Something",
            class_name="Blueprint", status=ObjectStatus(),
        )
        assert not handler.supports(obj, VersionContext())

    def test_enrichment(self):
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.handlers import run_handlers
        from uasset_read.v2.version import VersionContext

        doc = parse_package_document(str(SAMPLES_DIR / "Lyra_Enum_PanelType.uasset"))
        enums = [o for o in doc.objects if o.class_name == "UserDefinedEnum"]
        assert len(enums) >= 1
        obj = enums[0]
        semantic, _cov = run_handlers(obj, VersionContext(), doc.objects, doc.package)
        assert semantic is not None
        assert semantic["kind"] == "user_defined_enum"
        assert semantic["enum_name"] == "Enum_PanelType"


class TestUserDefinedStructHandler:
    def test_supports(self):
        from uasset_read.v2.handlers import UserDefinedStructHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = UserDefinedStructHandler()
        obj = ObjectRecord(
            id="export:0", table_index=0, name="Struct_Objective",
            class_name="UserDefinedStruct", status=ObjectStatus(),
        )
        assert handler.supports(obj, VersionContext())

    def test_rejects_non_struct(self):
        from uasset_read.v2.handlers import UserDefinedStructHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = UserDefinedStructHandler()
        obj = ObjectRecord(
            id="export:0", table_index=0, name="DT_Something",
            class_name="DataTable", status=ObjectStatus(),
        )
        assert not handler.supports(obj, VersionContext())

    def test_enrichment(self):
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.handlers import run_handlers
        from uasset_read.v2.version import VersionContext

        doc = parse_package_document(str(SAMPLES_DIR / "StackOBot_Struct_Objective.uasset"))
        structs = [o for o in doc.objects if o.class_name == "UserDefinedStruct"]
        assert len(structs) >= 1
        obj = structs[0]
        semantic, _cov = run_handlers(obj, VersionContext(), doc.objects, doc.package)
        assert semantic is not None
        assert semantic["kind"] == "user_defined_struct"
        assert semantic["struct_name"] == "Struct_Objective"


class TestTexture2DEnrichment:
    """Texture2D enrichment via depth=asset (properties parsed at object level)."""

    def test_texture2d_semantic_fields(self):
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.handlers import TextureHandler
        from uasset_read.v2.version import VersionContext

        doc = parse_package_document(
            str(SAMPLES_DIR / "FirstPerson_T_GridChecker_A.uasset"),
            depth="object",
        )
        tex_objs = [o for o in doc.objects if o.class_name == "Texture2D"]
        assert len(tex_objs) >= 1

        handler = TextureHandler()
        obj = tex_objs[0]
        ctx = VersionContext()
        result = handler.enrich(obj, ctx, doc.objects, None)

        assert result is not None
        assert result["kind"] == "texture"
        assert result["texture_type"] == "Texture2D"
        assert "srgb" in result
        assert isinstance(result["srgb"], bool)
        assert "compression_settings" in result

    def test_texture2d_coverage_entries(self):
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.handlers import TextureHandler
        from uasset_read.v2.version import VersionContext

        doc = parse_package_document(
            str(SAMPLES_DIR / "FirstPerson_T_GridChecker_A.uasset"),
            depth="object",
        )
        tex_objs = [o for o in doc.objects if o.class_name == "Texture2D"]
        obj = tex_objs[0]

        handler = TextureHandler()
        handler.enrich(obj, VersionContext(), doc.objects, None)

        feature_names = [c.feature for c in obj.coverage]
        assert "texture.kind" in feature_names
        assert "texture.texture_type" in feature_names
        assert "texture.srgb" in feature_names
        assert "texture.compression_settings" in feature_names

    def test_texture2d_no_properties_returns_none(self):
        from uasset_read.v2.handlers import TextureHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = TextureHandler()
        obj = ObjectRecord(
            id="export:0", table_index=0, name="Tex",
            class_name="Texture2D", status=ObjectStatus(),
            properties=None,
        )
        result = handler.enrich(obj, VersionContext(), [], None)
        assert result is None


class TestTextureCubeEnrichment:
    """TextureCube enrichment via depth=asset (properties parsed at object level)."""

    def test_texturecube_semantic_fields(self):
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.handlers import TextureHandler
        from uasset_read.v2.version import VersionContext

        doc = parse_package_document(
            str(SAMPLES_DIR / "MutableSample_GrayLightTextureCube.uasset"),
            depth="object",
        )
        tex_objs = [o for o in doc.objects if o.class_name == "TextureCube"]
        assert len(tex_objs) >= 1

        handler = TextureHandler()
        obj = tex_objs[0]
        ctx = VersionContext()
        result = handler.enrich(obj, ctx, doc.objects, None)

        assert result is not None
        assert result["kind"] == "texture"
        assert result["texture_type"] == "TextureCube"
        assert "srgb" in result
        assert isinstance(result["srgb"], bool)
        assert "compression_settings" in result

    def test_texturecube_coverage_entries(self):
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.handlers import TextureHandler
        from uasset_read.v2.version import VersionContext

        doc = parse_package_document(
            str(SAMPLES_DIR / "MutableSample_GrayLightTextureCube.uasset"),
            depth="object",
        )
        tex_objs = [o for o in doc.objects if o.class_name == "TextureCube"]
        obj = tex_objs[0]

        handler = TextureHandler()
        handler.enrich(obj, VersionContext(), doc.objects, None)

        feature_names = [c.feature for c in obj.coverage]
        assert "texture.kind" in feature_names
        assert "texture.texture_type" in feature_names
        assert "texture.srgb" in feature_names
        assert "texture.compression_settings" in feature_names

    def test_texturecube_payload_handler_returns_none_without_imported_size(self):
        """TextureCube without ImportedSize returns None from payload handler."""
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.handlers import TexturePayloadHandler
        from uasset_read.v2.version import VersionContext

        doc = parse_package_document(
            str(SAMPLES_DIR / "MutableSample_GrayLightTextureCube.uasset"),
            depth="object",
        )
        tex_objs = [o for o in doc.objects if o.class_name == "TextureCube"]
        obj = tex_objs[0]

        handler = TexturePayloadHandler()
        result = handler.enrich(obj, VersionContext(), doc.objects, None)

        # TextureCube doesn't have ImportedSize property, so result is None
        assert result is None


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


class TestMaterialHandler:
    def test_material_handler_supports(self):
        from uasset_read.v2.handlers import MaterialHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = MaterialHandler()
        obj = ObjectRecord(id="export:0", table_index=0, name="M_Test", class_name="Material", status=ObjectStatus())
        assert handler.supports(obj, VersionContext())

    def test_material_rejects_non_material(self):
        from uasset_read.v2.handlers import MaterialHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = MaterialHandler()
        obj = ObjectRecord(id="export:0", table_index=0, name="BP", class_name="Blueprint", status=ObjectStatus())
        assert not handler.supports(obj, VersionContext())

    def test_material_enrichment(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(
            str(SAMPLES_DIR / "FirstPerson_M_PrototypeGrid.uasset"), depth="asset"
        )
        mat_objs = [o for o in doc.objects if o.class_name == "Material"]
        assert len(mat_objs) >= 1
        obj = mat_objs[0]
        assert obj.semantic is not None
        assert obj.semantic["kind"] == "material"


class TestMaterialInstanceHandler:
    def test_material_instance_handler_supports(self):
        from uasset_read.v2.handlers import MaterialInstanceHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = MaterialInstanceHandler()
        obj = ObjectRecord(id="export:0", table_index=0, name="MI_Test", class_name="MaterialInstanceConstant", status=ObjectStatus())
        assert handler.supports(obj, VersionContext())

    def test_material_instance_rejects_non_instance(self):
        from uasset_read.v2.handlers import MaterialInstanceHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = MaterialInstanceHandler()
        obj = ObjectRecord(id="export:0", table_index=0, name="BP", class_name="Blueprint", status=ObjectStatus())
        assert not handler.supports(obj, VersionContext())

    def test_material_instance_enrichment(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(
            str(SAMPLES_DIR / "CassiniSample_MI_Template_BaseGray_Metal.uasset"), depth="asset"
        )
        mi_objs = [o for o in doc.objects if o.class_name == "MaterialInstanceConstant"]
        assert len(mi_objs) >= 1
        obj = mi_objs[0]
        assert obj.semantic is not None
        assert obj.semantic["kind"] == "material_instance"
