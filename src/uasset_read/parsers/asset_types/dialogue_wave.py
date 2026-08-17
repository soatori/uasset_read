"""UDialogueWave Asset type handler (opaque partial metadata).

UDialogueWave is a dialogue wave asset.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_dialogue_wave = make_opaque_stub("DialogueWave")
