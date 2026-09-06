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
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport

from uasset_read.parsers.asset_types.anim_common import ensure_custom_data
from uasset_read.parsers.asset_types.property_extractor import (
    build_properties_dict,
    extract_array_property,
    extract_property,
)
from uasset_read.parsers.class_registry import ClassHandler, HandlerResult

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


class MovieSceneHandler(ClassHandler):
    """UMovieScene Asset type handler"""

    def can_handle(self, class_name: str) -> bool:
        return class_name == "MovieScene"

    @property
    def handler_name(self) -> str:
        return "MovieSceneHandler"

    def parse(
        self,
        export: "ObjectExport",
        archive: "FArchive",
        context: Optional[Any] = None,
    ) -> HandlerResult:
        """Parse MovieScene export.

        Args:
            export: ObjectExport instance
            archive: Archive for reading (unused by this handler)
            context: parse context

        Returns:
            HandlerResult with success status and data
        """
        try:
            # Extract properties from export
            properties_list = getattr(export, "properties", [])
            if not properties_list:
                return HandlerResult(
                    success=False,
                    error_message="No properties found",
                )

            # Convert property list to dictionary format (name -> value)
            properties = build_properties_dict(properties_list)

            # Build MovieScene metadata
            data = SimpleNamespace(
                type="MovieScene",
                display_rate=None,
                tick_resolution=None,
                evaluation_type=None,
                clock_source=None,
                track_count=0,
                track_classes=[],
                spawnable_count=0,
                possessable_count=0,
                binding_count=0,
                marked_frame_count=0,
            )

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
            data.spawnable_count = len(
                extract_array_property(properties, "Spawnables", lambda x: x if isinstance(x, list) else [])
            )
            data.possessable_count = len(
                extract_array_property(properties, "Possessables", lambda x: x if isinstance(x, list) else [])
            )
            data.binding_count = len(
                extract_array_property(properties, "ObjectBindings", lambda x: x if isinstance(x, list) else [])
            )
            data.marked_frame_count = len(
                extract_array_property(properties, "MarkedFrames", lambda x: x if isinstance(x, list) else [])
            )

            # Store to export custom data
            ensure_custom_data(export)["movie_scene"] = vars(data)

            return HandlerResult(
                success=True,
                data={"movie_scene": vars(data)},
            )

        except (KeyError, TypeError, ValueError) as e:
            logger.warning("MovieScene parse error: %s", e)
            return HandlerResult(
                success=False,
                error_message=str(e),
            )
