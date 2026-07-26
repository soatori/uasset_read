"""SoundWave Asset metadata extractor (partial metadata).

Note: This module does not attempt to parse the UE standard USoundWave::Serialize layout.
Only extracts raw byte samples for diagnostics.
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_sound_wave = make_opaque_stub("SoundWave")
