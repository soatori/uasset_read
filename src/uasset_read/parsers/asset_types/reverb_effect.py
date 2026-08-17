"""UReverbEffect Asset type handler (opaque partial metadata).

UReverbEffect defines reverb effect settings.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_reverb_effect = make_opaque_stub("ReverbEffect")
