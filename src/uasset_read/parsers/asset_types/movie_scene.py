"""UMovieScene Asset type handler

Parse UMovieScene tagged properties data:
- DisplayRate: FFrameRate (display frame rate, Numerator + Denominator)
- TickResolution: FFrameRate (tick resolution, Numerator + Denominator)
- EvaluationType: EMovieSceneEvaluationType (evaluation type)
- ClockSource: EUpdateClockSource (clock source)
- Tracks: TArray<UMovieSceneTrack> (track list, extract class names)
- Spawnables: TArray<FMovieSceneSpawnable> (spawnable objects)
- Possessables: TArray<FMovieScenePossessable> (possessable objects)

Format reference:
- Engine/Source/Runtime/MovieScene/Public/MovieScene.h
- Engine/Source/Runtime/MovieScene/Private/MovieScene.cpp
"""
from __future__ import annotations

import logging
from typing import Any

from uasset_read.models.fallback import ExportParseStatus as ParseStatus
from uasset_read.parsers.asset_types.anim_common import ensure_custom_data
from uasset_read.parsers.asset_types.property_extractor import (
    build_properties_dict,
    extract_array_property,
    extract_property,
)

logger = logging.getLogger(__name__)


def _parse_frame_rate(value: Any) -> dict | None:
    """Parse FFrameRate property value (dict or list/tuple)."""
    if isinstance(value, dict):
        return {
            "numerator": value.get("Numerator", 0),
            "denominator": value.get("Denominator", 1),
        }
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return {
            "numerator": value[0],
            "denominator": value[1],
        }
    return None


def _parse_track_classes(value: Any) -> list[str]:
    """Extract track class names from Tracks array."""
    if not isinstance(value, list):
        return []
    return [
        cls
        for track in value
        if isinstance(track, dict)
        for cls in [track.get("class_name") or track.get("class")]
        if cls
    ]


class _MovieSceneData:
    """MovieScene parse result container, supports setattr access for extract_property."""

    __slots__ = (
        "display_rate", "tick_resolution", "evaluation_type", "clock_source",
        "track_count", "track_classes", "spawnable_count", "possessable_count",
        "binding_count", "marked_frame_count",
    )

    def __init__(self) -> None:
        self.display_rate = None
        self.tick_resolution = None
        self.evaluation_type = None
        self.clock_source = None
        self.track_count = 0
        self.track_classes: list[str] = []
        self.spawnable_count = 0
        self.possessable_count = 0
        self.binding_count = 0
        self.marked_frame_count = 0

    def to_dict(self) -> dict[str, Any]:
        return {"type": "MovieScene", **{slot: getattr(self, slot) for slot in self.__slots__}}


class MovieSceneHandler:
    """UMovieScene Asset type handler"""

    # Reflection registration metadata
    export_type: str = "MovieScene"
    priority: int = 100

    def handle(self, export: Any, context: Any) -> ParseStatus:
        """Handle MovieScene export.

        Args:
            export: ObjectExport instance
            context: parse context

        Returns:
            ParseStatus: SUCCESS or PARTIAL
        """
        try:
            # Extract properties from export
            properties_list = getattr(export, "properties", [])
            if not properties_list:
                return ParseStatus.PARTIAL

            # Convert property list to dictionary format (name -> value)
            properties = build_properties_dict(properties_list)

            # Build MovieScene metadata
            data = _MovieSceneData()

            # FFrameRate property extraction
            extract_property(properties, "DisplayRate", data, "display_rate", transform=_parse_frame_rate)
            extract_property(properties, "TickResolution", data, "tick_resolution", transform=_parse_frame_rate)

            # Simple property extraction
            extract_property(properties, "EvaluationType", data, "evaluation_type")
            extract_property(properties, "ClockSource", data, "clock_source")

            # Array property extraction (Tracks also extracts class names)
            tracks = extract_array_property(properties, "Tracks", _parse_track_classes)
            data.track_count = len(tracks)
            data.track_classes = tracks

            # Array length extraction
            data.spawnable_count = len(extract_array_property(properties, "Spawnables", lambda x: x if isinstance(x, list) else []))
            data.possessable_count = len(extract_array_property(properties, "Possessables", lambda x: x if isinstance(x, list) else []))
            data.binding_count = len(extract_array_property(properties, "ObjectBindings", lambda x: x if isinstance(x, list) else []))
            data.marked_frame_count = len(extract_array_property(properties, "MarkedFrames", lambda x: x if isinstance(x, list) else []))

            # Store to export custom data
            ensure_custom_data(export)["movie_scene"] = data.to_dict()

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            # Log error and record in context warnings for visibility
            logger.warning("MovieScene parse error: %s", e)
            if hasattr(context, "warnings"):
                context.warnings.append(f"MovieScene parse error: {e}")
            return ParseStatus.PARTIAL
