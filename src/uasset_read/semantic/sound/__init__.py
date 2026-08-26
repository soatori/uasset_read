"""Sound semantic JSON domain (#557c)."""

from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.sound.extractor import build_sound_content

for _class in ("SoundWave", "SoundCue", "SoundAttenuation"):
    register_extension(
        _class,
        build_sound_content,
        domain_format="uasset_read.sound_semantic",
        domain_format_version="1.0.0",
    )
