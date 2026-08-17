"""UMediaPlayer type handler (opaque partial metadata).

UMediaPlayer handles video/audio playback.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_media_player = make_opaque_stub("MediaPlayer")
