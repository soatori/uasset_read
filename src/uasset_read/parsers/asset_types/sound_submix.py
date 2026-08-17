"""USoundSubmix type handler (opaque partial metadata).

USoundSubmix defines audio submix routing and effects.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_sound_submix = make_opaque_stub("SoundSubmix")
