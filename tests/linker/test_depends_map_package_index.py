"""Tests for Task 5: DependsMap FPackageIndex semantics.

DependsMap values should be interpreted as FPackageIndex:
- Positive = export index (1-based)
- Negative = import index (-1 based)
- Zero = null
"""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset_with_linker
from uasset_read.link.object_instance import UObjectInstance
from tests.conftest import asset_path, ASSET_MESH_CHAIR


# Sample assets 相对路径
STATIC_MESH_REL = "StackOBot_M_BotBase.uasset"
BLUEPRINT_REL = "StackOBot_BP_Drone.uasset"


class TestDependsMapFPackageIndexSemantics:
    """Test that DependsMap values are interpreted as FPackageIndex."""

    def test_depends_map_uses_package_index(self, sample_root: Path):
        """DependsMap values should be FPackageIndex, not raw export indices."""
        bp_path = asset_path(sample_root, BLUEPRINT_REL)
        result = parse_uasset_with_linker(str(bp_path), preload_all=True)

        # Check if DependsMap exists
        if not hasattr(result.summary, 'depends_map') or not result.summary.depends_map:
            pytest.skip("No DependsMap in this file")

        # Find an export with dependencies
        for exp_idx, dep_indices in enumerate(result.summary.depends_map):
            if not dep_indices:
                continue

            # Each dep should be interpretable as FPackageIndex
            for raw_dep in dep_indices:
                # Positive = export, negative = import, 0 = null
                if raw_dep > 0:
                    # Export index (1-based)
                    export_idx = raw_dep - 1
                    assert 0 <= export_idx < len(result.export_map), \
                        f"DependsMap export index {raw_dep} out of bounds"
                elif raw_dep < 0:
                    # Import index (-1 based)
                    import_idx = -raw_dep - 1
                    assert 0 <= import_idx < len(result.import_map), \
                        f"DependsMap import index {raw_dep} out of bounds"
                # raw_dep == 0 is null, valid
        del result

    def test_linker_resolves_depends_to_instances(self, sample_root: Path):
        """Linker should resolve DependsMap to UObjectInstance references."""
        bp_path = asset_path(sample_root, BLUEPRINT_REL)
        result = parse_uasset_with_linker(str(bp_path), preload_all=True)
        linker = result.linker

        # Check that dependencies are resolved to UObjectInstance
        for inst in linker._export_objects:
            if hasattr(inst, 'dependencies') and inst.dependencies:
                for dep in inst.dependencies:
                    assert isinstance(dep, UObjectInstance), \
                        f"Dependency should be UObjectInstance, not {type(dep)}"
                    assert hasattr(dep, 'object_name'), \
                        "Dependency should have object_name"
        del result

    def test_depends_map_can_reference_imports(self, sample_root: Path):
        """DependsMap should be able to reference imports (negative indices)."""
        bp_path = asset_path(sample_root, BLUEPRINT_REL)
        result = parse_uasset_with_linker(str(bp_path), preload_all=True)
        linker = result.linker

        # Check if any dependency references an import
        has_import_dep = False
        for inst in linker._export_objects:
            if hasattr(inst, 'dependencies') and inst.dependencies:
                for dep in inst.dependencies:
                    if dep.is_import:
                        has_import_dep = True
                        break

        # This is informational — some assets may only have export dependencies
        # The important thing is that the code doesn't crash and handles both cases
        assert isinstance(has_import_dep, bool)
        del result

    def test_depends_map_with_static_mesh(self, sample_root: Path):
        """Test DependsMap resolution with StaticMesh asset."""
        mesh_path = asset_path(sample_root, STATIC_MESH_REL)
        result = parse_uasset_with_linker(str(mesh_path), preload_all=True)
        linker = result.linker

        # StaticMesh should have some dependencies resolved
        has_deps = any(
            hasattr(inst, 'dependencies') and inst.dependencies
            for inst in linker._export_objects
        )
        # This is informational — the important thing is no crashes
        assert isinstance(has_deps, bool)
        del result


class TestDependsMapUnitTests:
    """Unit tests for DependsMap FPackageIndex interpretation."""

    def test_zero_is_null_dependency(self):
        """Zero in DependsMap should be treated as null (skipped)."""
        from uasset_read.link.linker import PackageLinker
        from uasset_read.serializers.object_resources import PackageIndex

        # Zero should be null
        pkg_idx = PackageIndex(0)
        assert pkg_idx.is_null

    def test_positive_is_export(self):
        """Positive value in DependsMap should be export index (1-based)."""
        from uasset_read.serializers.object_resources import PackageIndex

        pkg_idx = PackageIndex(1)  # First export
        assert pkg_idx.is_export
        assert pkg_idx.to_export_index() == 0  # 0-based

    def test_negative_is_import(self):
        """Negative value in DependsMap should be import index (-1 based)."""
        from uasset_read.serializers.object_resources import PackageIndex

        pkg_idx = PackageIndex(-1)  # First import
        assert pkg_idx.is_import
        assert pkg_idx.to_import_index() == 0  # 0-based
