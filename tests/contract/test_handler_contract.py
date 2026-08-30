"""Handler contract — DataTable, Texture, Sound real samples and handler failure isolation."""

from __future__ import annotations

from pathlib import Path

import pytest


SAMPLES_DIR = Path(__file__).parent.parent / "samples"


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
        from uasset_read.v2.handlers import run_handlers, register_handler, get_handlers
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

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


class TestUserDefinedEnumHandler:
    def test_supports(self):
        from uasset_read.v2.handlers import UserDefinedEnumHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = UserDefinedEnumHandler()
        obj = ObjectRecord(
            id="export:1",
            table_index=1,
            name="Enum_PanelType",
            class_name="UserDefinedEnum",
            status=ObjectStatus(),
        )
        assert handler.supports(obj, VersionContext())

    def test_rejects_non_enum(self):
        from uasset_read.v2.handlers import UserDefinedEnumHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = UserDefinedEnumHandler()
        obj = ObjectRecord(
            id="export:0",
            table_index=0,
            name="BP_Something",
            class_name="Blueprint",
            status=ObjectStatus(),
        )
        assert not handler.supports(obj, VersionContext())

    def test_enrichment(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "Lyra_Enum_PanelType.uasset"))
        enums = [o for o in doc.objects if o.class_name == "UserDefinedEnum"]
        assert len(enums) >= 1
        obj = enums[0]
        # Handlers run during parse_package_document; check semantic on object
        assert obj.semantic is not None
        assert obj.semantic["kind"] == "user_defined_enum"
        assert obj.semantic["enum_name"] == "Enum_PanelType"


class TestUserDefinedStructHandler:
    def test_supports(self):
        from uasset_read.v2.handlers import UserDefinedStructHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = UserDefinedStructHandler()
        obj = ObjectRecord(
            id="export:0",
            table_index=0,
            name="Struct_Objective",
            class_name="UserDefinedStruct",
            status=ObjectStatus(),
        )
        assert handler.supports(obj, VersionContext())

    def test_rejects_non_struct(self):
        from uasset_read.v2.handlers import UserDefinedStructHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = UserDefinedStructHandler()
        obj = ObjectRecord(
            id="export:0",
            table_index=0,
            name="DT_Something",
            class_name="DataTable",
            status=ObjectStatus(),
        )
        assert not handler.supports(obj, VersionContext())

    def test_enrichment(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "StackOBot_Struct_Objective.uasset"))
        structs = [o for o in doc.objects if o.class_name == "UserDefinedStruct"]
        assert len(structs) >= 1
        obj = structs[0]
        # Handlers run during parse_package_document; check semantic on object
        assert obj.semantic is not None
        assert obj.semantic["kind"] == "user_defined_struct"
        assert obj.semantic["struct_name"] == "Struct_Objective"


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
            id="export:0",
            table_index=0,
            name="Tex",
            class_name="Texture2D",
            status=ObjectStatus(),
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


class TestSkeletonHandler:
    def test_skeleton_handler_supports(self):
        from uasset_read.v2.handlers import SkeletonHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = SkeletonHandler()
        obj = ObjectRecord(id="export:0", table_index=0, name="SK", class_name="Skeleton", status=ObjectStatus())
        assert handler.supports(obj, VersionContext())

    def test_skeleton_rejects_non_skeleton(self):
        from uasset_read.v2.handlers import SkeletonHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = SkeletonHandler()
        obj = ObjectRecord(id="export:0", table_index=0, name="BP", class_name="Blueprint", status=ObjectStatus())
        assert not handler.supports(obj, VersionContext())

    def test_skeleton_enrichment(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "ALS_Mannequin_Skeleton.uasset"), depth="asset")
        skel_objs = [o for o in doc.objects if o.class_name == "Skeleton"]
        assert len(skel_objs) >= 1
        obj = skel_objs[0]
        assert obj.semantic is not None
        assert obj.semantic["kind"] == "skeleton"
        assert "bone_count" in obj.semantic


class TestMeshHandler:
    def test_mesh_handler_supports_static(self):
        from uasset_read.v2.handlers import MeshHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = MeshHandler()
        obj = ObjectRecord(id="export:0", table_index=0, name="SM", class_name="StaticMesh", status=ObjectStatus())
        assert handler.supports(obj, VersionContext())

    def test_mesh_handler_supports_skeletal(self):
        from uasset_read.v2.handlers import MeshHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = MeshHandler()
        obj = ObjectRecord(id="export:0", table_index=0, name="SKM", class_name="SkeletalMesh", status=ObjectStatus())
        assert handler.supports(obj, VersionContext())

    def test_mesh_rejects_non_mesh(self):
        from uasset_read.v2.handlers import MeshHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = MeshHandler()
        obj = ObjectRecord(id="export:0", table_index=0, name="BP", class_name="Blueprint", status=ObjectStatus())
        assert not handler.supports(obj, VersionContext())

    def test_static_mesh_enrichment(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "StarterContent_SM_Chair.uasset"), depth="asset")
        mesh_objs = [o for o in doc.objects if o.class_name == "StaticMesh"]
        assert len(mesh_objs) >= 1
        obj = mesh_objs[0]
        assert obj.semantic is not None
        assert obj.semantic["kind"] == "mesh"
        assert obj.semantic["mesh_type"] == "StaticMesh"

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

        doc = parse_package_document(str(SAMPLES_DIR / "FirstPerson_M_PrototypeGrid.uasset"), depth="asset")
        mat_objs = [o for o in doc.objects if o.class_name == "Material"]
        assert len(mat_objs) >= 1
        obj = mat_objs[0]
        assert obj.semantic is not None
        assert obj.semantic["kind"] == "material"


class TestHandlerWiringFromPublicAPI:
    def test_datatable_handler_runs_from_public_api(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "ALS_FootstepDataTable.uasset"), depth="asset")
        dt_objs = [o for o in doc.objects if o.class_name == "DataTable"]
        assert len(dt_objs) >= 1
        obj = dt_objs[0]
        assert obj.semantic is not None
        assert obj.semantic["kind"] == "data_table"
        assert obj.status.semantic == "complete"

    def test_handler_exception_becomes_object_diagnostic(self, monkeypatch):
        import uasset_read.v2.handlers as handlers
        from uasset_read.v2.api import parse_package_document

        # We need to re-register a bad handler, then restore after
        class RaisingHandler:
            def supports(self, obj, context):
                return True

            def enrich(self, obj, context, all_objects, package_data):
                raise ValueError("broken handler")

        original_handlers = list(handlers._HANDLERS)
        try:
            handlers._HANDLERS.append(RaisingHandler())
            sample_doc = parse_package_document(
                str(SAMPLES_DIR / "ALS_FootstepDataTable.uasset"),
                depth="object",
                object_ids=["export:0"],
            )
            from uasset_read.v2.version import VersionContext

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


class TestMaterialInstanceHandler:
    def test_material_instance_handler_supports(self):
        from uasset_read.v2.handlers import MaterialInstanceHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = MaterialInstanceHandler()
        obj = ObjectRecord(
            id="export:0", table_index=0, name="MI_Test", class_name="MaterialInstanceConstant", status=ObjectStatus()
        )
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


class TestSkeletonSummaryConsistency:
    def test_skeleton_summary_is_internally_consistent(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "ALS_Mannequin_Skeleton.uasset"), depth="asset")
        obj = next(o for o in doc.objects if o.class_name == "Skeleton")
        assert obj.semantic is not None
        assert obj.semantic["kind"] == "skeleton"
        assert obj.semantic["bone_count"] == len(obj.semantic["bones"])
        assert obj.semantic["bone_count"] > 0


class TestStaticMeshSummaryConsistency:
    def test_static_mesh_summary_is_internally_consistent(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "StarterContent_SM_Chair.uasset"), depth="asset")
        obj = next(o for o in doc.objects if o.class_name == "StaticMesh")
        assert obj.semantic is not None
        assert obj.semantic["kind"] == "mesh"
        assert obj.semantic["lod_count"] == len(obj.semantic["lods"])


class TestSampleBackedHandlers:
    """Strict real-sample assertions for all sample-backed handlers."""

    @pytest.mark.parametrize(
        ("sample", "class_name", "expected_kind"),
        [
            ("ALS_FootstepDataTable.uasset", "DataTable", "data_table"),
            ("Lyra_Enum_PanelType.uasset", "UserDefinedEnum", "user_defined_enum"),
            ("StackOBot_Struct_Objective.uasset", "UserDefinedStruct", "user_defined_struct"),
            ("FirstPerson_T_GridChecker_A.uasset", "Texture2D", "texture"),
            ("MutableSample_GrayLightTextureCube.uasset", "TextureCube", "texture"),
            ("ALS_Concrete_Step_01_SoundWave.uasset", "SoundWave", "sound"),
        ],
    )
    def test_sample_backed_handler(self, sample, class_name, expected_kind):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / sample), depth="asset")
        obj = next(o for o in doc.objects if o.class_name == class_name)
        assert obj.semantic is not None
        assert obj.semantic["kind"] == expected_kind
        assert obj.coverage

    def test_datatable_row_count_invariant(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "ALS_FootstepDataTable.uasset"), depth="asset")
        dt = next(o for o in doc.objects if o.class_name == "DataTable")
        assert dt.semantic is not None
        # row_count should be non-negative
        assert dt.semantic["row_count"] >= 0

    def test_texture_dimensions_positive(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "FirstPerson_T_GridChecker_A.uasset"), depth="asset")
        tex = next(o for o in doc.objects if o.class_name == "Texture2D")
        assert tex.semantic is not None
        assert tex.semantic["kind"] == "texture"
        assert tex.semantic["texture_type"] == "Texture2D"
        # srgb should be a bool
        assert isinstance(tex.semantic["srgb"], bool)

    def test_sound_has_coverage(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "ALS_Concrete_Step_01_SoundWave.uasset"), depth="asset")
        sw = next(o for o in doc.objects if o.class_name == "SoundWave")
        assert sw.semantic is not None
        assert sw.semantic["kind"] == "sound"
        assert sw.semantic["sound_type"] == "SoundWave"
        assert sw.coverage  # has at least one coverage entry

    def test_handler_exception_becomes_object_diagnostic(self, monkeypatch):
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
                str(SAMPLES_DIR / "ALS_FootstepDataTable.uasset"),
                depth="object",
                object_ids=["export:0"],
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


class TestAnimBlueprintDepthContract:
    """Test that AnimBlueprint handlers respect depth parameter."""

    def test_asset_depth_omits_heavy_graph_arrays(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset"), depth="asset")
        obj = next(o for o in doc.objects if o.class_name == "AnimBlueprintGeneratedClass")
        assert obj.semantic is not None
        assert obj.semantic["kind"] == "anim_blueprint"
        # At depth=asset, no heavy graph arrays should be present
        assert "nodes" not in obj.semantic
        assert "bytecode" not in obj.semantic
        assert "graph" not in obj.semantic

    def test_decode_graph_references_existing_nodes(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(
            str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset"),
            depth="decode",
            object_ids=["export:2"],
        )
        # export:2 is AnimBlueprintGeneratedClass
        obj = doc.objects[2]
        assert obj.semantic is not None
        assert obj.semantic["kind"] == "anim_blueprint"
        # At depth=decode, graph data should be present
        if "graph" in obj.semantic:
            graph = obj.semantic["graph"]
            assert "nodes" in graph
            assert "edges" in graph
            # Verify all edge references point to existing nodes
            node_ids = {node["id"] for node in graph["nodes"]}
            for edge in graph["edges"]:
                assert edge["from_node"] in node_ids, f"Edge from_node {edge['from_node']} not in nodes"
                assert edge["to_node"] in node_ids, f"Edge to_node {edge['to_node']} not in nodes"

    def test_animbp_handler_supports(self):
        from uasset_read.v2.handlers import AnimBlueprintHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = AnimBlueprintHandler()
        obj = ObjectRecord(
            id="export:0",
            table_index=0,
            name="ABP_Test",
            class_name="AnimBlueprintGeneratedClass",
            status=ObjectStatus(),
        )
        assert handler.supports(obj, VersionContext())

    def test_animbp_handler_rejects_non_animbp(self):
        from uasset_read.v2.handlers import AnimBlueprintHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = AnimBlueprintHandler()
        obj = ObjectRecord(
            id="export:0", table_index=0, name="SM_Chair", class_name="StaticMesh", status=ObjectStatus()
        )
        assert not handler.supports(obj, VersionContext())


class TestBlueprintDepthContract:
    """Test that Blueprint handlers respect depth parameter."""

    def test_blueprint_handler_supports(self):
        from uasset_read.v2.handlers import BlueprintHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = BlueprintHandler()
        obj = ObjectRecord(
            id="export:0", table_index=0, name="BP_Test", class_name="BlueprintGeneratedClass", status=ObjectStatus()
        )
        assert handler.supports(obj, VersionContext())

    def test_blueprint_handler_rejects_non_blueprint(self):
        from uasset_read.v2.handlers import BlueprintHandler
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus
        from uasset_read.v2.version import VersionContext

        handler = BlueprintHandler()
        obj = ObjectRecord(
            id="export:0", table_index=0, name="SM_Chair", class_name="StaticMesh", status=ObjectStatus()
        )
        assert not handler.supports(obj, VersionContext())
