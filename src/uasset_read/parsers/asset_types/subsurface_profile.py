"""USubsurfaceProfile Asset type handler (opaque partial metadata).

Pure UPROPERTY serialization, no custom Serialize().
Defines subsurface scattering material profile parameters.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_subsurface_profile = make_opaque_stub("SubsurfaceProfile")
