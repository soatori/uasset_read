"""
游戏版本映射 — 通过游戏标识推断 PAK 文件版本。

参考 external/CUE4Parse/CUE4Parse/UE4/Versions/EGame.cs 实现。
"""

from typing import Dict, Optional, Tuple
from uasset_read.pak.constants import PakFileVersion


# 游戏标识枚举（简化版，仅包含常用游戏）
class EGame:
    """游戏标识枚举。"""
    UNKNOWN = 0
    OUTLAST_TRIALS = 1
    TORCHLIGHT_INFINITE = 2
    WILD_ASSAULT = 3
    GAMELOOP_UNDAWN = 4
    FRIDAY_THE_13TH = 5
    DREAM_STAR = 6
    GAME_FOR_PEACE = 7
    KART_RIDER_DRIFT = 8
    RACING_MASTER = 9
    CRYSTAL_OF_ATLAN = 10
    PROMISE_MASCOT_AGENCY = 11
    ARENA_BREAKOUT_INFINITE = 12
    ASSAULT_FIRE_FUTURE = 13
    # 可以继续添加更多游戏


# 游戏到 PAK 版本的映射
GAME_PAK_VERSION_MAP: Dict[int, int] = {
    EGame.UNKNOWN: PakFileVersion.Utf8PakDirectory,  # 默认最新版本
    EGame.OUTLAST_TRIALS: PakFileVersion.PathHashIndex,
    EGame.TORCHLIGHT_INFINITE: PakFileVersion.PathHashIndex,
    EGame.WILD_ASSAULT: PakFileVersion.PathHashIndex,
    EGame.GAMELOOP_UNDAWN: PakFileVersion.PathHashIndex,
    EGame.FRIDAY_THE_13TH: PakFileVersion.RelativeChunkOffsets,
    EGame.DREAM_STAR: PakFileVersion.PathHashIndex,
    EGame.GAME_FOR_PEACE: PakFileVersion.FNameBasedCompressionMethod,
    EGame.KART_RIDER_DRIFT: PakFileVersion.PathHashIndex,
    EGame.RACING_MASTER: PakFileVersion.PathHashIndex,
    EGame.CRYSTAL_OF_ATLAN: PakFileVersion.PathHashIndex,
    EGame.PROMISE_MASCOT_AGENCY: PakFileVersion.PathHashIndex,
    EGame.ARENA_BREAKOUT_INFINITE: PakFileVersion.PathHashIndex,
    EGame.ASSAULT_FIRE_FUTURE: PakFileVersion.PathHashIndex,
}


# 魔数到游戏标识的映射
MAGIC_TO_GAME_MAP: Dict[int, int] = {
    0xA590ED1E: EGame.OUTLAST_TRIALS,
    0x6B2A56B8: EGame.TORCHLIGHT_INFINITE,
    0xA4CCD123: EGame.WILD_ASSAULT,
    0x5A6F12EC: EGame.GAMELOOP_UNDAWN,
    0x65617441: EGame.FRIDAY_THE_13TH,
    0x1B6A32F1: EGame.DREAM_STAR,
    0xFF67FF70: EGame.GAME_FOR_PEACE,
    0x81C4B35B: EGame.KART_RIDER_DRIFT,
    0x9A51DA3F: EGame.RACING_MASTER,
    0x22CE976A: EGame.CRYSTAL_OF_ATLAN,
    0x11ADDE11: EGame.PROMISE_MASCOT_AGENCY,
    0x53647586: EGame.ARENA_BREAKOUT_INFINITE,
    0x4F6FAE86: EGame.ASSAULT_FIRE_FUTURE,
}


def detect_game_from_magic(magic: int) -> int:
    """根据魔数检测游戏标识。

    Args:
        magic: PAK 文件魔数

    Returns:
        游戏标识（EGame 枚举值）
    """
    return MAGIC_TO_GAME_MAP.get(magic, EGame.UNKNOWN)


def get_pak_version_for_game(game: int) -> int:
    """获取游戏对应的 PAK 版本。

    Args:
        game: 游戏标识（EGame 枚举值）

    Returns:
        PAK 文件版本（PakFileVersion 枚举值）
    """
    return GAME_PAK_VERSION_MAP.get(game, PakFileVersion.Utf8PakDirectory)


def get_game_info(game: int) -> Tuple[str, int]:
    """获取游戏信息。

    Args:
        game: 游戏标识（EGame 枚举值）

    Returns:
        (游戏名称, PAK 版本)
    """
    game_names = {
        EGame.UNKNOWN: "Unknown",
        EGame.OUTLAST_TRIALS: "Outlast Trials",
        EGame.TORCHLIGHT_INFINITE: "Torchlight Infinite",
        EGame.WILD_ASSAULT: "Wild Assault",
        EGame.GAMELOOP_UNDAWN: "Gameloop Undawn",
        EGame.FRIDAY_THE_13TH: "Friday the 13th",
        EGame.DREAM_STAR: "Dream Star",
        EGame.GAME_FOR_PEACE: "Game for Peace",
        EGame.KART_RIDER_DRIFT: "KartRider Drift",
        EGame.RACING_MASTER: "Racing Master",
        EGame.CRYSTAL_OF_ATLAN: "Crystal of Atlan",
        EGame.PROMISE_MASCOT_AGENCY: "Promise Mascot Agency",
        EGame.ARENA_BREAKOUT_INFINITE: "Arena Breakout Infinite",
        EGame.ASSAULT_FIRE_FUTURE: "Assault Fire Future",
    }
    name = game_names.get(game, "Unknown")
    version = get_pak_version_for_game(game)
    return name, version
