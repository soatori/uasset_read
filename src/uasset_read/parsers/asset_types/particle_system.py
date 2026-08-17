"""UParticleSystem type handler (opaque partial metadata).

UParticleSystem is the legacy Cascade particle system.
Already in _OPAQUE_CLASSES; this provides the parser stub and kinds mapping.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_particle_system = make_opaque_stub("ParticleSystem")
