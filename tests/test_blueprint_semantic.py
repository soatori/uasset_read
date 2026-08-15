
class TestBlueprintComponents:
    def test_component_emission_and_parent_resolution(self):
        from uasset_read.semantic.blueprint.components import emit_components
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        source = [
            {"name": "CollisionCylinder", "class": "CapsuleComponent"},
            {"name": "Mesh", "class": "SkeletalMeshComponent",
             "parent": "CollisionCylinder", "socket": "WeaponSocket"},
        ]
        rep = BlueprintReporting()
        comps = emit_components(source, TypeTable(), rep)
        assert comps[0]["id"] == "c0"
        assert comps[0]["origin"] == "unverified"
        assert comps[0]["type"] == {"$type": "t0"}
        assert comps[1]["parent"] == "c0"
        assert comps[1]["socket"] == "WeaponSocket"
        assert [e["scope"] for e in rep.coverage_entries()] == ["components"]

    def test_dangling_parent_diagnosed(self):
        from uasset_read.semantic.blueprint.components import emit_components
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        rep = BlueprintReporting()
        comps = emit_components([{"name": "Mesh", "class": "X", "parent": "Nope"}],
                                TypeTable(), rep)
        assert "parent" not in comps[0]
        assert any(d["code"] == "BP_COMPONENT_PARENT_UNRESOLVED"
                   for d in rep.diagnostics_entries("standard"))
