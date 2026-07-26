"""ULevelSequence Asset type handler

Parse ULevelSequence custom serialization data:
- MovieScene: int32 (opaque pointer, pointing to UMovieScene object)
- MovieSceneSource: int32 (TSoftObjectPtr, asset source reference)
- MovieSceneLicense: FString (license string)
- DisplayRate: FFrameRate (display frame rate, Numerator + Denominator each int32)
- TickResolution: FFrameRate (tick resolution, Numerator + Denominator each int32)

Format reference:
- Engine/Source/Runtime/LevelSequence/Classes/LevelSequence.h
- Engine/Source/Runtime/LevelSequence/Private/LevelSequence.cpp
"""

import logging
import struct
from typing import Any, Dict, List

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)


def parse_level_sequence(archive: Any, name_map: List[str]) -> Dict[str, Any]:
    """Parse ULevelSequence asset custom serialization data.

    Args:
        archive: FArchive instance (positioned at export serial_offset)
        name_map: name table

    Returns:
        Parse result dictionary containing movie_scene, movie_scene_source,
        movie_scene_license, display_rate, tick_resolution and other fields
    """
    result: Dict[str, Any] = {
        "parse_status": "success",
    }

    try:
        # 1. MovieScene: int32 — opaque pointer to UMovieScene
        #    LevelSequence.cpp: ULevelSequence::Serialize serializes MovieScene pointer
        result["movie_scene"] = archive.read_i32("LevelSequence.MovieScene")

        # 2. MovieSceneSource: TSoftObjectPtr — asset source reference (serialized as int32 object index)
        result["movie_scene_source"] = archive.read_i32("LevelSequence.MovieSceneSource")

        # 3. MovieSceneLicense: FString — license string
        result["movie_scene_license"] = archive.read_fstring("LevelSequence.MovieSceneLicense")

        # 4. DisplayRate: FFrameRate — display frame rate
        display_rate_num = archive.read_i32("LevelSequence.DisplayRate.Numerator")
        display_rate_den = archive.read_i32("LevelSequence.DisplayRate.Denominator")
        result["display_rate"] = {
            "numerator": display_rate_num,
            "denominator": display_rate_den,
        }

        # 5. TickResolution: FFrameRate — tick resolution
        tick_resolution_num = archive.read_i32("LevelSequence.TickResolution.Numerator")
        tick_resolution_den = archive.read_i32("LevelSequence.TickResolution.Denominator")
        result["tick_resolution"] = {
            "numerator": tick_resolution_num,
            "denominator": tick_resolution_den,
        }

    except (struct.error, OSError, ValueError, ParseError) as e:
        logger.debug("LevelSequence handler parse failed: %s", e)
        result["parse_status"] = "failed"
        result["error"] = str(e)

    return result
