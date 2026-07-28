"""Compatibility fallback for SoundCue native serialization.

SoundCue tagged properties are projected by ``PropertyMetadataHandler``.  Its
native graph payload is version-dependent and must not be read as a fixed
``FirstNode, Volume, Pitch`` byte sequence.
"""

from typing import Any


def parse_sound_cue(archive: Any, name_map: list[str]) -> dict[str, str]:
    """Return an honest opaque fallback without consuming native bytes."""
    return {"asset_type": "SoundCue", "parse_status": "opaque"}
