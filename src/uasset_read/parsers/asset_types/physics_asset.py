"""UPhysicsAsset type handler (opaque partial metadata).

UPhysicsAsset contains collision body and constraint data for skeletal meshes.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_physics_asset = make_opaque_stub("PhysicsAsset")
