"""UMediaSource type handler (opaque partial metadata).

UMediaSource is the base class for media URL/file sources.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_media_source = make_opaque_stub("MediaSource")
