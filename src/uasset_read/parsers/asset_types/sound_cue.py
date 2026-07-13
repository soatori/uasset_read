"""USoundCue 资产类型处理器

解析 USoundCue 的 custom serialization 数据：
- FirstNode: int32（opaque pointer，SoundCue 节点图的根节点）
- VolumeMultiplier: float（音量倍增器）
- PitchMultiplier: float（音高倍增器）
- SoundCueNodes: TArray<int32>（节点数组，每项为节点对象引用）

格式参考：
- Engine/Source/Runtime/Engine/Classes/Sound/SoundCue.h
- Engine/Source/Runtime/Engine/Private/Sound/SoundCue.cpp
"""

import logging
import struct
from typing import Any, Dict, List

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)


def parse_sound_cue(archive: Any, name_map: List[str]) -> Dict[str, Any]:
    """解析 USoundCue 资产的 custom serialization 数据。

    Args:
        archive: FArchive 实例（已定位到 export 的 serial_offset）
        name_map: 名称表

    Returns:
        解析结果字典，包含 first_node、volume_multiplier、pitch_multiplier、sound_cue_nodes 等
    """
    result: Dict[str, Any] = {
        "parse_status": "success",
    }

    try:
        # 1. FirstNode: int32 — opaque pointer to the first SoundCue node
        #    SoundCue.cpp: USoundCue::Serialize 起始位置
        result["first_node"] = archive.read_i32("SoundCue.FirstNode")

        # 2. VolumeMultiplier: float (f32)
        result["volume_multiplier"] = archive.read_f32("SoundCue.VolumeMultiplier")

        # 3. PitchMultiplier: float (f32)
        result["pitch_multiplier"] = archive.read_f32("SoundCue.PitchMultiplier")

        # 4. SoundCueNodes: TArray<int32> — 节点对象引用数组
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
        logger.debug("SoundCue handler 解析失败: %s", e)
        result["parse_status"] = "failed"
        result["error"] = str(e)

    return result
