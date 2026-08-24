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
from typing import Any, Dict, List, Optional

from uasset_read.exceptions import ParseError

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


def _extract_property(properties: List[Any], name: str) -> Optional[Any]:
    """Extract a named property value from parsed property list.

    Args:
        properties: PropertyValue list (from property parser)
        name: Property name (e.g. "SampleRate")

    Returns:
        Property value or None
    """
    for prop in properties:
        if hasattr(prop, "name") and prop.name == name:
            return getattr(prop, "value", None)
    return None


def _extract_bool(properties: List[Any], name: str) -> bool:
    """Extract a boolean value from the property list."""
    val = _extract_property(properties, name)
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val != 0
    return bool(val)


def _extract_int(properties: List[Any], name: str) -> Optional[int]:
    """Extract an int value from the property list."""
    val = _extract_property(properties, name)
    if val is None:
        return None
    if isinstance(val, int):
        return val
    return None


def _extract_float(properties: List[Any], name: str) -> Optional[float]:
    """Extract a float value from the property list."""
    val = _extract_property(properties, name)
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _extract_enum(properties: List[Any], name: str, enum_map: Dict[int, str]) -> Optional[str]:
    """Extract an enum value name from the property list."""
    val = _extract_property(properties, name)
    if val is None:
        return None
    # EnumValue wrapper
    if hasattr(val, "value_name"):
        return val.value_name
    if isinstance(val, int):
        return enum_map.get(val, f"Unknown({val})")
    if isinstance(val, str):
        return val
    return None


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

    # Basic audio properties (SoundWave.h:791-822)
    sample_rate = _extract_int(properties, "SampleRate")
    if sample_rate is not None:
        sound["sample_rate"] = sample_rate

    imported_sample_rate = _extract_int(properties, "ImportedSampleRate")
    if imported_sample_rate is not None:
        sound["imported_sample_rate"] = imported_sample_rate

    num_channels = _extract_int(properties, "NumChannels")
    if num_channels is not None:
        sound["num_channels"] = num_channels

    duration = _extract_float(properties, "Duration")
    if duration is not None:
        sound["duration"] = duration

    # Playback controls (SoundWave.h:782-788)
    volume = _extract_float(properties, "Volume")
    if volume is not None:
        sound["volume"] = volume

    pitch = _extract_float(properties, "Pitch")
    if pitch is not None:
        sound["pitch"] = pitch

    # Compression format (SoundWave.h:424-468)
    compression_type = _extract_enum(
        properties, "SoundAssetCompressionType", _COMPRESSION_TYPE_NAMES
    )
    if compression_type is not None:
        sound["compression_type"] = compression_type

    compression_quality = _extract_int(properties, "CompressionQuality")
    if compression_quality is not None:
        sound["compression_quality"] = compression_quality

    # Playback flags (SoundWave.h:446-455) — only output when True
    b_looping = _extract_bool(properties, "bLooping")
    if b_looping:
        sound["looping"] = True

    b_streaming = _extract_bool(properties, "bStreaming")
    if b_streaming:
        sound["streaming"] = True

    b_procedural = _extract_bool(properties, "bProcedural")
    if b_procedural:
        sound["procedural"] = True

    # Sound group (SoundWave.h:442)
    sound_group = _extract_enum(properties, "SoundGroup", _SOUND_GROUP_NAMES)
    if sound_group is not None:
        sound["sound_group"] = sound_group

    # Subtitle properties (SoundWave.h:685-779)
    subtitle_priority = _extract_float(properties, "SubtitlePriority")
    if subtitle_priority is not None:
        sound["subtitle_priority"] = subtitle_priority

    b_mature = _extract_bool(properties, "bMature")
    if b_mature:
        sound["mature"] = True

    # Loading behavior from UPROPERTY (SoundWave.h:760-761)
    loading_behavior = _extract_enum(
        properties, "LoadingBehavior", _LOADING_BEHAVIOR_NAMES
    )
    if loading_behavior is not None:
        sound["loading_behavior"] = loading_behavior

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
