"""Unit tests for Diagnostic.reason (quality system)."""

from uasset_read.models.diagnostics import Diagnostic, make_diagnostic


def test_reason_omitted_from_dict_when_unset():
    d = make_diagnostic("SOME_CODE", "msg", "objects.export")
    assert d.reason is None
    payload = d.to_dict()
    assert "reason" not in payload


def test_reason_included_when_set():
    d = make_diagnostic(
        "EXPORT_TRAILING_BYTES_UNCONSUMED",
        "leaves 53 bytes",
        "objects.export",
        reason="editor_only",
    )
    assert d.reason == "editor_only"
    assert d.to_dict()["reason"] == "editor_only"


def test_make_diagnostic_accepts_reason_keyword():
    d = Diagnostic(
        severity="warning",
        code="name_index_out_of_range",
        message="bad index",
        stage="read_name",
        reason="recovered_corruption",
    )
    assert d.reason == "recovered_corruption"


def test_fname_out_of_range_carries_recovered_corruption_reason(tmp_path):
    # Build a minimal ByteArchive-like path is heavy; call _record on FArchive subclass.
    from uasset_read.archive import FArchive

    class _Mem(FArchive):
        def __init__(self):
            self._init_archive_attrs(path="<mem>", tolerant=True)
            self._file = None

    arch = _Mem()
    arch._current_object_id = "export:1"
    arch._record_structured_diagnostic(
        code="name_index_out_of_range",
        stage="read_name",
        offset=16,
        raw_value=3223003549,
        fallback="used_default_name",
        message="Name index out of range",
        reason="recovered_corruption",
    )
    (diag,) = arch.get_structured_diagnostics()
    assert diag.reason == "recovered_corruption"
    assert diag.code == "name_index_out_of_range"


def test_classify_trailing_reason_mapping():
    from uasset_read.models.diagnostics import classify_trailing_reason

    assert classify_trailing_reason("PackageMetaData") == "editor_only"
    assert classify_trailing_reason("MetaData") == "editor_only"
    assert classify_trailing_reason("FontFace") == "bulk_expected"
    assert classify_trailing_reason("SoundWave") == "bulk_expected"
    assert classify_trailing_reason("Texture2D") == "bulk_expected"
    assert classify_trailing_reason("TextureCube") == "bulk_expected"
    assert classify_trailing_reason("TextureRenderTarget2D") == "bulk_expected"
    assert classify_trailing_reason("BlendSpace") == "known_unimplemented"
    assert classify_trailing_reason("BlendSpace1D") == "known_unimplemented"
    assert classify_trailing_reason("AnimSequence") == "known_unimplemented"
    assert classify_trailing_reason("AnimMontage") == "known_unimplemented"
    assert classify_trailing_reason("AnimBlueprint") == "editor_only"
    assert classify_trailing_reason("Material") == "known_unimplemented"
    assert classify_trailing_reason("MaterialInstanceConstant") == "known_unimplemented"
    assert classify_trailing_reason("MaterialFunction") == "known_unimplemented"
    assert classify_trailing_reason("NiagaraNodeFunctionCall") == "known_unimplemented"
    assert classify_trailing_reason("NiagaraNodeAssignment") == "known_unimplemented"
    assert classify_trailing_reason("Skeleton") == "known_unimplemented"
    assert classify_trailing_reason("PhysicsAsset") == "known_unimplemented"
    assert classify_trailing_reason("BlueprintGeneratedClass") == "editor_only"
    assert classify_trailing_reason("K2Node_CallFunction") == "editor_only"
    assert classify_trailing_reason("EdGraph") == "editor_only"
    assert classify_trailing_reason("SomeUnknownClass") == "unexpected"


def test_merge_archive_recoveries_forwards_reason_and_fallback():
    from types import SimpleNamespace

    from uasset_read.models.diagnostics import Diagnostic
    from uasset_read.parsers.legacy_reader import _merge_archive_recoveries

    sd = Diagnostic(
        severity="warning",
        code="name_index_out_of_range",
        message="Name index out of range fallback=used_default_name",
        stage="read_name",
        object_id="export:1",
        offset=16,
        fallback="used_default_name",
        reason="recovered_corruption",
    )
    archive = SimpleNamespace(get_structured_diagnostics=lambda: [sd])
    diagnostics: list[Diagnostic] = []
    _merge_archive_recoveries(archive, [], diagnostics)
    (merged,) = diagnostics
    assert merged.code == "name_index_out_of_range"
    assert merged.reason == "recovered_corruption"
    assert merged.fallback == "used_default_name"
    assert merged.effect == "recovery"
    assert merged.recoverable is True


def test_merge_archive_recoveries_stop_table_keeps_reason():
    from types import SimpleNamespace

    from uasset_read.models.diagnostics import Diagnostic
    from uasset_read.parsers.legacy_reader import _merge_archive_recoveries

    sd = Diagnostic(
        severity="error",
        code="export_table_truncated",
        message="truncated",
        stage="export_table",
        object_id="export:2",
        offset=100,
        fallback="stop_table",
        reason="recovered_corruption",
    )
    archive = SimpleNamespace(get_structured_diagnostics=lambda: [sd])
    diagnostics: list[Diagnostic] = []
    _merge_archive_recoveries(archive, [], diagnostics)
    (merged,) = diagnostics
    assert merged.reason == "recovered_corruption"
    assert merged.fallback == "stop_table"
    assert merged.effect == "data_loss"
    assert merged.recoverable is False


def test_table_payload_residue_emits_conservative_complete_reason():
    """Residue is fully disclosed; the parser stopped conservatively, not corruptly."""
    import struct

    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.legacy_reader import _read_table_rows

    # One valid row then 2 undecoded bytes -> TABLE_PAYLOAD_RESIDUE (+ TRUNCATED).
    data = struct.pack("<i", 1) + struct.pack("<ii", 1, 0) + struct.pack("<ii", 0, 0) + b"\x7f\x7f"
    diags: list = []
    _read_table_rows(
        ByteArchive(data),
        serial_end=len(data),
        name_map=["None", "RowA"],
        object_id="export:1",
        diagnostics=diags,
    )
    residue_diags = [d for d in diags if d.code == "TABLE_PAYLOAD_RESIDUE"]
    assert residue_diags, f"expected TABLE_PAYLOAD_RESIDUE, got {[d.code for d in diags]}"
    assert all(d.reason == "conservative_complete" for d in residue_diags)


def test_table_rows_truncated_emits_conservative_complete_reason():
    """Row shortfall is disclosed as conservative stop, not silent data loss."""
    import struct

    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.legacy_reader import _read_table_rows

    # Claims 2 rows, only 1 fits -> TABLE_ROWS_TRUNCATED, no residue.
    data = struct.pack("<i", 2) + struct.pack("<ii", 1, 0) + struct.pack("<ii", 0, 0)
    diags: list = []
    _read_table_rows(
        ByteArchive(data),
        serial_end=len(data),
        name_map=["None", "A"],
        object_id="export:1",
        diagnostics=diags,
    )
    truncated = [d for d in diags if d.code == "TABLE_ROWS_TRUNCATED"]
    assert truncated, f"expected TABLE_ROWS_TRUNCATED, got {[d.code for d in diags]}"
    assert all(d.reason == "conservative_complete" for d in truncated)


def test_datatable_table_diagnostics_marked_conservative_complete():
    from uasset_read.package import parse_package_document

    doc = parse_package_document("tests/samples/FirstPerson_DT_WeaponList.uasset")
    table_diags = [
        d for d in doc.diagnostics if d.code in {"TABLE_PAYLOAD_RESIDUE", "TABLE_ROWS_TRUNCATED"}
    ]
    # Fixture may or may not emit both; assert every emitted TABLE_* is classified.
    assert all(d.reason == "conservative_complete" for d in table_diags)
    if not table_diags:
        # Force one synthetic check that make_diagnostic can carry the reason.
        from uasset_read.models.diagnostics import make_diagnostic

        d = make_diagnostic("TABLE_ROWS_TRUNCATED", "m", "payload.table", reason="conservative_complete")
        assert d.reason == "conservative_complete"


def test_bp_combat_character_trailing_diagnostics_carry_reason():
    from uasset_read.package import parse_package_document

    doc = parse_package_document("tests/samples/BP_CombatCharacter.uasset", depth="asset")
    trailing = [d for d in doc.diagnostics if d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED"]
    assert trailing, "expected trailing diagnostics on this fixture"
    assert all(d.reason is not None for d in trailing)
    assert {"editor_only", "bulk_expected", "known_unimplemented", "unexpected"} & {
        d.reason for d in trailing
    }


def test_bp_seeds_have_zero_fstring_all_null():
    from pathlib import Path

    from uasset_read.package import parse_package_document

    samples = Path("tests/samples")
    names = (
        "BP_CombatCharacter.uasset",
        "BP_CombatEnemy.uasset",
        "LevelDesign_ABP_Manny.uasset",
    )
    for name in names:
        doc = parse_package_document(str(samples / name), depth="asset")
        codes = [d.code for d in doc.diagnostics]
        assert "fstring_all_null" not in codes, f"{name}: {codes.count('fstring_all_null')} fstring_all_null"


def test_bp_combat_character_category_text_still_decodes():
    from uasset_read.package import parse_package_document

    doc = parse_package_document("tests/samples/BP_CombatCharacter.uasset", depth="asset")
    export = next(o for o in doc.objects if o.id == "export:1")
    nv_prop = (export.properties or {}).get("NewVariables")
    # NewVariables is an ArrayProperty wrapper: {kind, type, value: [...]}
    entries = nv_prop.get("value", []) if isinstance(nv_prop, dict) else []
    categories = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        fields = entry.get("fields") or {}
        cat = fields.get("Category")
        if isinstance(cat, dict) and cat.get("kind") == "text":
            categories.append(cat)
    assert categories, "expected at least one FText Category on NewVariables"
    for cat in categories:
        assert cat.get("namespace") == ""
        assert "key" in cat, cat
        assert "source_string" in cat, cat
    assert any(c.get("key") for c in categories), categories
    assert any(c.get("source_string") for c in categories), categories


def test_als_animbp_has_no_name_index_out_of_range():
    from uasset_read.package import parse_package_document

    doc = parse_package_document("tests/samples/ALS_AnimBP.uasset", depth="asset")
    codes = [d.code for d in doc.diagnostics]
    assert "name_index_out_of_range" not in codes, (
        [d.message for d in doc.diagnostics if d.code == "name_index_out_of_range"]
    )


def test_als_animbp_ordered_saved_pose_indices_map_keys():
    from uasset_read.package import parse_package_document

    doc = parse_package_document("tests/samples/ALS_AnimBP.uasset", depth="asset")
    export = next(o for o in doc.objects if o.id == "export:281")
    prop = (export.properties or {}).get("OrderedSavedPoseIndicesMap")
    assert prop is not None, "OrderedSavedPoseIndicesMap missing on ALS_AnimBP_C"
    # Property wrapper: {kind, type, value: MapValue{entries: [{key, value}]}}
    bag = prop["value"] if isinstance(prop, dict) and "value" in prop else prop
    entries = bag["entries"] if isinstance(bag, dict) and "entries" in bag else bag
    assert isinstance(entries, list) and len(entries) >= 9, entries
    keys = [e.get("key") for e in entries if isinstance(e, dict)]
    assert "AnimGraph" in keys, keys
    # At least one entry should expose OrderedSavedPoseNodeIndices after the fix
    sample = next(e for e in entries if e.get("key") == "AnimGraph")
    value = sample.get("value")
    fields = value.get("fields") if isinstance(value, dict) else getattr(value, "fields", None)
    assert fields is not None, value
    assert "OrderedSavedPoseNodeIndices" in fields, fields


def test_classify_trailing_reason_accepts_trailing_context():
    from uasset_read.models.diagnostics import TrailingContext, classify_trailing_reason

    ctx = TrailingContext(
        class_name="FontFace",
        object_name="MyFont",
        outer_name="/Game/Fonts/F",
        roles=("asset",),
        payload_kind="native_serial",
    )
    assert classify_trailing_reason(ctx) == "bulk_expected"


def test_classify_trailing_reason_context_defaults_match_class_name_shorthand():
    from uasset_read.models.diagnostics import TrailingContext, classify_trailing_reason

    for cls, expected in (
        ("TextureCube", "bulk_expected"),
        ("K2Node_CallFunction", "editor_only"),
        ("Skeleton", "known_unimplemented"),
        ("SomeUnknownClass", "unexpected"),
    ):
        assert classify_trailing_reason(TrailingContext(class_name=cls)) == expected
        assert classify_trailing_reason(cls) == expected


def test_resolve_outer_name_export_and_import_and_null():
    from uasset_read.models.object_model import ObjectRecord, ObjectRef
    from uasset_read.parsers.legacy_reader import _resolve_outer_name
    from uasset_read.serializers.object_resources import ObjectImport, PackageIndex

    objects = [
        ObjectRecord(id="export:0", table_index=0, name="Root", roles=("asset",)),
        ObjectRecord(
            id="export:1", table_index=1, name="Child",
            outer_ref=ObjectRef(table="export", index=0), roles=(),
        ),
    ]
    imports = [
        ObjectImport(
            class_package="/Script/Engine", class_name="Class",
            outer_index=PackageIndex(0), object_name="SomeClass",
        )
    ]
    # Export Outer resolves through the objects list.
    assert _resolve_outer_name(objects[1], objects, imports) == "Root"
    # Import Outer resolves through the import map.
    obj_import_outer = ObjectRecord(
        id="export:2", table_index=2, name="Inst",
        outer_ref=ObjectRef(table="import", index=0), roles=(),
    )
    assert _resolve_outer_name(obj_import_outer, objects, imports) == "SomeClass"
    # Null Outer and out-of-range indexes stay None (bounded, no raise).
    assert _resolve_outer_name(objects[0], objects, imports) is None
    obj_oob = ObjectRecord(
        id="export:3", table_index=3, name="OOB",
        outer_ref=ObjectRef(table="export", index=99), roles=(),
    )
    assert _resolve_outer_name(obj_oob, objects, imports) is None


def test_make_diagnostic_accepts_size():
    from uasset_read.models.diagnostics import make_diagnostic

    d = make_diagnostic(
        "EXPORT_TRAILING_BYTES_UNCONSUMED", "leaves 6 bytes",
        "objects.export", size=6, reason="editor_only",
    )
    assert d.size == 6
    assert d.to_dict()["size"] == 6
