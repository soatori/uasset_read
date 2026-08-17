"""USoundMix type handler (opaque partial metadata).

USoundMix defines audio mixing settings (EQ, volume adjustments).
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_sound_mix = make_opaque_stub("SoundMix")
