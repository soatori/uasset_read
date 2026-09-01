"""USoundWave asset type handler.

Parses USoundWave custom serialization data:
- Flags: uint32 — bit-packed (CookedFlag, HasOwnerLoadingBehaviorFlag, LoadingBehavior)
- Conditional fields read based on Flags and version

Also extracts semantic metadata from parsed UPROPERTY tagged properties:
- SampleRate, NumChannels, Duration, Volume, Pitch
- SoundAssetCompressionType, CompressionQuality
- bLooping, bStreaming, SoundGroup

Format reference:
- Engine/Source/Runtime/Engine/Classes/Sound/SoundWave.h
- Engine/Source/Runtime/Engine/Private/Sound/SoundWave.cpp (USoundWave::Serialize)
"""

import logging
import struct
from typing import Any, Callable, Dict, List, Optional

from uasset_read.exceptions import ParseError
from uasset_read.parsers.asset_types.property_extractor import build_properties_dict

logger = logging.getLogger(__name__)

# --- Flags bit definitions (SoundWave.cpp:1269-1276) ---
_COOKED_FLAG = 1 << 0
_HAS_OWNER_LOADING_BEHAVIOR_FLAG = 1 << 1
_LOADING_BEHAVIOR_SHIFT = 2
_LOADING_BEHAVIOR_MASK = 0b00000111

# Compression type enum values (SoundWave.h:348-366)
_COMPRESSION_TYPE_NAMES = {
    0: "BinkAudio",
    1: "ADPCM",
    2: "PCM",
    3: "Opus",
    4: "PlatformSpecific",
    5: "ProjectDefined",
    6: "RADAudio",
}

# Loading behavior enum values (SoundWaveLoadingBehavior.h:22-37)
_LOADING_BEHAVIOR_NAMES = {
    0: "Inherited",
    1: "RetainOnLoad",
    2: "PrimeOnLoad",
    3: "LoadOnDemand",
    4: "ForceInline",
    0xFF: "Uninitialized",
}

# Sound group enum values (SoundGroups.h)
_SOUND_GROUP_NAMES = {
    0: "Default",
    1: "UI",
    2: "Ambient",
    3: "ForceMono",
    4: "SFX",
    5: "Music",
}


def _as_int(value: Any) -> Optional[int]:
    return value if isinstance(value, int) else None


def _as_float(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) else None


def _as_flag(value: Any) -> Optional[bool]:
    """Coerce to bool; only True is projected (caller skips None)."""
    if value is None:
        return None
    return True if value else None


def _as_enum(value: Any, enum_map: Dict[int, str]) -> Optional[str]:
    if value is None:
        return None
    # EnumValue wrapper
    if hasattr(value, "value_name"):
        return value.value_name
    if isinstance(value, int):
        return enum_map.get(value, f"Unknown({value})")
    if isinstance(value, str):
        return value
    return None


# (UPROPERTY name, semantic key, value coercion); fields are skipped when the
# coercion yields None.
_SOUND_FIELDS: tuple[tuple[str, str, Callable[[Any], Any]], ...] = (
    ("SampleRate", "sample_rate", _as_int),
    ("ImportedSampleRate", "imported_sample_rate", _as_int),
    ("NumChannels", "num_channels", _as_int),
    ("Duration", "duration", _as_float),
    ("Volume", "volume", _as_float),
    ("Pitch", "pitch", _as_float),
    ("SoundAssetCompressionType", "compression_type", lambda v: _as_enum(v, _COMPRESSION_TYPE_NAMES)),
    ("CompressionQuality", "compression_quality", _as_int),
    ("bLooping", "looping", _as_flag),
    ("bStreaming", "streaming", _as_flag),
    ("bProcedural", "procedural", _as_flag),
    ("SoundGroup", "sound_group", lambda v: _as_enum(v, _SOUND_GROUP_NAMES)),
    ("SubtitlePriority", "subtitle_priority", _as_float),
    ("bMature", "mature", _as_flag),
    ("LoadingBehavior", "loading_behavior", lambda v: _as_enum(v, _LOADING_BEHAVIOR_NAMES)),
)


def parse_sound_wave(
    archive: Any,
    name_map: List[str],
    export: Optional[Any] = None,
) -> Dict[str, Any]:
    """Parse USoundWave asset custom serialization data.

    Args:
        archive: FArchive instance (positioned after Super::Serialize custom payload)
        name_map: Name table
        export: ObjectExport instance (optional, for extracting UPROPERTY properties)

    Returns:
        Parsed result dictionary with sound semantic metadata
    """
    result: Dict[str, Any] = {
        "parse_status": "success",
        "format": "uasset_read.sound_flags_only",
    }

    # === Custom Serialize data (after Super::Serialize / tagged properties) ===
    # SoundWave.cpp:1278-1302 — Flags uint32
    try:
        flags = archive.read_u32("SoundWave.Flags")
    except (struct.error, OSError, ParseError) as e:
        logger.debug("SoundWave: failed to read Flags: %s", e)
        result["parse_status"] = "partial"
        result["error"] = f"Failed to read Flags: {e}"
        return result

    is_cooked = bool(flags & _COOKED_FLAG)
    has_owner_loading_behavior = bool(flags & _HAS_OWNER_LOADING_BEHAVIOR_FLAG)
    loading_behavior_value = (flags >> _LOADING_BEHAVIOR_SHIFT) & _LOADING_BEHAVIOR_MASK

    handler_data: Dict[str, Any] = {
        "flags": flags,
        "is_cooked": is_cooked,
        "has_owner_loading_behavior": has_owner_loading_behavior,
    }

    if has_owner_loading_behavior:
        handler_data["owner_loading_behavior"] = _LOADING_BEHAVIOR_NAMES.get(
            loading_behavior_value, f"Unknown({loading_behavior_value})"
        )

    result.update(handler_data)

    # === Build sound semantic metadata (extracted from UPROPERTY properties) ===
    properties: List[Any] = []
    if export is not None:
        properties = getattr(export, "properties", [])

    if properties:
        sound_metadata = build_sound_metadata(handler_data, properties)
        if sound_metadata:
            result["sound"] = sound_metadata
            result["format"] = "uasset_read.sound_semantic"
        else:
            # Properties exist but no usable sound fields
            pass
    else:
        # No properties available — flags only
        pass

    return result


def build_sound_metadata(
    handler_data: Dict[str, Any],
    properties: List[Any],
) -> Dict[str, Any]:
    """Build sound semantic metadata from handler data and UPROPERTY properties.

    This is the core of sound_semantic format: ensures output always contains
    a non-empty sound block.

    Args:
        handler_data: Custom serialize data from parse_sound_wave()
        properties: Parsed UPROPERTY tagged properties

    Returns:
        Sound semantic metadata dictionary (guaranteed non-empty)
    """
    sound: Dict[str, Any] = {}

    # --- Extract semantic fields from UPROPERTY tagged properties ---
    values = build_properties_dict(list(properties))
    for prop_name, field, coerce in _SOUND_FIELDS:
        val = coerce(values.get(prop_name))
        if val is not None:
            sound[field] = val

    sample_rate = sound.get("sample_rate")
    duration = sound.get("duration")
    num_channels = sound.get("num_channels")

    # --- Supplement from custom serialize data ---
    if handler_data.get("is_cooked") is not None:
        sound["is_cooked"] = handler_data["is_cooked"]

    if handler_data.get("owner_loading_behavior") is not None:
        sound["owner_loading_behavior"] = handler_data["owner_loading_behavior"]

    # Derived information
    if sample_rate is not None and duration is not None and duration > 0:
        sound["estimated_frame_count"] = int(sample_rate * duration)

    # Channel layout
    if num_channels is not None:
        if num_channels == 1:
            sound["channel_layout"] = "mono"
        elif num_channels == 2:
            sound["channel_layout"] = "stereo"
        elif num_channels == 5:
            sound["channel_layout"] = "5.1"
        elif num_channels == 7:
            sound["channel_layout"] = "7.1"
        else:
            sound["channel_layout"] = f"{num_channels}ch"

    return sound
