"""USoundClass type handler (opaque partial metadata).

USoundClass defines audio class hierarchy with volume/pitch modifiers.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_sound_class = make_opaque_stub("SoundClass")
