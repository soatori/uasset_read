"""USoundConcurrency Asset type handler (opaque partial metadata).

USoundConcurrency defines sound concurrency settings.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_sound_concurrency = make_opaque_stub("SoundConcurrency")
