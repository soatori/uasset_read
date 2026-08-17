"""UPhysicalMaterial type handler (opaque partial metadata).

UPhysicalMaterial defines friction, restitution, and density properties.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_physical_material = make_opaque_stub("PhysicalMaterial")
