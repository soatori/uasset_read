"""UAnimComposite Asset type handler (opaque partial metadata).

UAnimComposite combines multiple animations into a single unit.
Contains FAnimTrack with section/anim pairing.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_anim_composite = make_opaque_stub("AnimComposite")
