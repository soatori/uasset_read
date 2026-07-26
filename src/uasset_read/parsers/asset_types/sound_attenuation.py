"""SoundAttenuation Asset metadata extractor (partial metadata).

USoundAttenuation uses standard UPROPERTY serialization (no custom Serialize()),
currently only extracts raw byte samples for diagnostics.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_sound_attenuation = make_opaque_stub("SoundAttenuation")
