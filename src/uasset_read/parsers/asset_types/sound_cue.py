"""USoundCue Asset type handler

Parse USoundCue custom serialization data:
- FirstNode: int32 (opaque pointer, root node of the SoundCue node graph)
- VolumeMultiplier: float (volume multiplier)
- PitchMultiplier: float (pitch multiplier)
- SoundCueNodes: TArray<int32> (node array, each item is a node object reference)

Format reference:
- Engine/Source/Runtime/Engine/Classes/Sound/SoundCue.h
- Engine/Source/Runtime/Engine/Private/Sound/SoundCue.cpp
"""

import logging
import struct
from typing import Any, Dict, List

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)


def parse_sound_cue(archive: Any, name_map: List[str]) -> Dict[str, Any]:
    """Parse USoundCue asset custom serialization data.

    Args:
        archive: FArchive instance (positioned at export's serial_offset)
        name_map: Name table

    Returns:
        Parse result dictionary containing first_node, volume_multiplier, pitch_multiplier, sound_cue_nodes etc.
    """
    result: Dict[str, Any] = {
        "parse_status": "success",
    }

    try:
        # 1. FirstNode: int32 -- opaque pointer to the first SoundCue node
        #    SoundCue.cpp: USoundCue::Serialize start position
        result["first_node"] = archive.read_i32("SoundCue.FirstNode")

        # 2. VolumeMultiplier: float (f32)
        result["volume_multiplier"] = archive.read_f32("SoundCue.VolumeMultiplier")

        # 3. PitchMultiplier: float (f32)
        result["pitch_multiplier"] = archive.read_f32("SoundCue.PitchMultiplier")

        # 4. SoundCueNodes: TArray<int32> -- node object reference array
        node_count = archive.read_i32("SoundCue.SoundCueNodes.Count")

        if node_count < 0 or node_count > 10000:
            result["parse_status"] = "partial"
            result["error"] = f"Invalid node count: {node_count}"
            result["sound_cue_nodes"] = []
            result["node_count"] = node_count
            return result

        result["node_count"] = node_count
        nodes: List[int] = []
        for i in range(node_count):
            node_ref = archive.read_i32(f"SoundCue.SoundCueNodes[{i}]")
            nodes.append(node_ref)
        result["sound_cue_nodes"] = nodes

    except (struct.error, OSError, ValueError, ParseError) as e:
        logger.debug("SoundCue handler Parse failed: %s", e)
        result["parse_status"] = "failed"
        result["error"] = str(e)

    return result
