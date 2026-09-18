"""Per-export byte accounting scopes and physical source mapping."""

from __future__ import annotations

from tests.fixtures import parse_sample


def test_every_requested_export_scope_is_fully_tiled():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    scopes = document.byte_accounting.scopes
    expected = {obj.id for obj in document.objects if obj.serial_region and obj.serial_region.size > 0}
    assert expected
    assert expected <= set(scopes)
    for object_id in expected:
        scope = scopes[object_id]
        assert scope.leaves, f"{object_id} has no accounting leaves"
        scope.validate_full_coverage()


def test_unknown_tail_is_a_reasoned_leaf():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    for scope in document.byte_accounting.scopes.values():
        for leaf in scope.leaves:
            assert leaf.status in {"decoded", "opaque", "payload", "unavailable"}
            assert leaf.size > 0
            assert leaf.status == "decoded" or leaf.reason


def test_file_backed_leaf_preserves_physical_source_mapping():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    leaves = [leaf for scope in document.byte_accounting.scopes.values() for leaf in scope.leaves]
    assert leaves
    assert all(leaf.source_id for leaf in leaves)
    assert all(leaf.source_start is not None for leaf in leaves)


def test_cross_segment_region_retains_all_physical_slices(fake_source):
    from uasset_read.models.byte_ranges import region_from_source

    # fake_source: A.uasset=2 + A.uexp=3 bytes → virtual [0,5) crosses the boundary.
    region = region_from_source(fake_source, start=0, size=5, status="decoded")
    assert [(item.source_id, item.size) for item in region.source_slices] == [
        ("A.uasset", 2),
        ("A.uexp", 3),
    ]
