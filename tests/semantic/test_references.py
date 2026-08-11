"""Tests for reference table builder."""
from uasset_read.semantic.references import ReferenceTable
from uasset_read.models.ir import ImportIR, ExportIR


class TestReferenceTable:
    def test_collect_empty(self):
        table = ReferenceTable()
        refs = table.collect([], [])
        assert refs == ()

    def test_collect_imports(self):
        imports = [
            ImportIR(
                index=0,
                class_package="/Script/Engine",
                class_name="Class",
                object_name="Object",
                outer_index_resolved=None,
            ),
            ImportIR(
                index=1,
                class_package="/Game/T_Default",
                class_name="Texture2D",
                object_name="T_Default",
                outer_index_resolved=None,
            ),
        ]
        table = ReferenceTable()
        refs = table.collect(imports, [])
        assert len(refs) == 2
        assert refs[0].kind == "import"
        assert refs[0].class_name == "Class"
        assert refs[0].object_name == "Object"
        assert refs[0].package_path == "/Script/Engine"
        assert refs[1].kind == "import"
        assert refs[1].class_name == "Texture2D"

    def test_collect_exports(self):
        exports = [
            ExportIR(
                index=0,
                object_name="M_Default",
                object_class="Material",
                serial_size=1024,
                outer_index_resolved=None,
                super_index_resolved=None,
                parent_class=None,
                properties=[],
                graphs=[],
                bulk_data=None,
            ),
        ]
        table = ReferenceTable()
        refs = table.collect([], exports)
        assert len(refs) == 1
        assert refs[0].kind == "export"
        assert refs[0].class_name == "Material"
        assert refs[0].object_name == "M_Default"

    def test_deduplicates_by_index(self):
        imports = [
            ImportIR(
                index=0,
                class_package="/Script/Engine",
                class_name="Class",
                object_name="Object",
                outer_index_resolved=None,
            ),
        ]
        table = ReferenceTable()
        # Collect twice — should deduplicate
        refs1 = table.collect(imports, [])
        refs2 = table.collect(imports, [])
        # Third collect should not add duplicates
        all_refs = table.collect(imports, [])
        assert len(all_refs) == 1

    def test_mixed_imports_and_exports(self):
        imports = [
            ImportIR(
                index=0,
                class_package="/Script/Engine",
                class_name="Class",
                object_name="Object",
                outer_index_resolved=None,
            ),
        ]
        exports = [
            ExportIR(
                index=0,
                object_name="M_Default",
                object_class="Material",
                serial_size=1024,
                outer_index_resolved=None,
                super_index_resolved=None,
                parent_class=None,
                properties=[],
                graphs=[],
                bulk_data=None,
            ),
        ]
        table = ReferenceTable()
        refs = table.collect(imports, exports)
        assert len(refs) == 2
        # Sorted by (kind, index): export first (alphabetically before import)
        assert refs[0].kind == "export"
        assert refs[1].kind == "import"

    def test_sorted_by_kind_and_index(self):
        imports = [
            ImportIR(
                index=1,
                class_package="/Script/Engine",
                class_name="Class",
                object_name="Object",
                outer_index_resolved=None,
            ),
            ImportIR(
                index=0,
                class_package="/Game/T_Default",
                class_name="Texture2D",
                object_name="T_Default",
                outer_index_resolved=None,
            ),
        ]
        table = ReferenceTable()
        refs = table.collect(imports, [])
        assert len(refs) == 2
        # Should be sorted by (kind, index)
        assert refs[0].index == 0
        assert refs[1].index == 1
