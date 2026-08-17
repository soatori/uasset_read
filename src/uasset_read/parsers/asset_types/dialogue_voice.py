"""UDialogueVoice Asset type handler (opaque partial metadata).

UDialogueVoice is a dialogue voice asset.
Pure UPROPERTY serialization, no custom Serialize().
"""

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_dialogue_voice = make_opaque_stub("DialogueVoice")
