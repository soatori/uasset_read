"""
Game version mapping -- infer PAK file version from game identifier.

Reference: external/CUE4Parse/CUE4Parse/UE4/Versions/EGame.cs implementation.
"""

from typing import Dict, Tuple
from uasset_read.pak.constants import PakFileVersion


# Game identifier enumeration
class EGame:
    """Game identifier enumeration."""
    UNKNOWN = 0

    # Custom magic games (13, fully aligned with CUE4Parse FPakInfo.cs)
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

    # UE5 popular games (standard magic 0x5A6F12E1)
    BLACK_MYTH_WUKONG = 100
    STALKER_2 = 101
    MARVEL_RIVALS = 102
    THE_FIRST_DESCENDANT = 103
    INFINITY_NIKKI = 104
    WUTHERING_WAVES = 105
    DELTA_FORCE = 106
    SILENT_HILL_2_REMAKE = 107
    DUNE_AWAKENING = 108
    BORDERLANDS_4 = 109
    GRAY_ZONE_WARFARE = 110

    # UE4 popular games (standard magic 0x5A6F12E1)
    PUBG = 200
    FORTNITE = 201
    APEX_LEGENDS = 202
    KINGDOM_HEARTS_3 = 203
    FF7_REMAKE = 204
    GTA_TRILOGY = 205
    HOGWARTS_LEGACY = 206
    VALORANT = 207
    STATE_OF_DECAY_2 = 208
    DAYS_GONE = 209
    TEKKEN_7 = 210
    BORDERLANDS_3 = 211


# Game to PAK version mapping
# UE source reference: external/CUE4Parse/CUE4Parse/UE4/Versions/EGame.cs GetVersion()
GAME_PAK_VERSION_MAP: Dict[int, int] = {
    # Custom magic games
    EGame.UNKNOWN: PakFileVersion.Utf8PakDirectory,
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
    # UE5 games (file_version_ue5 mapping)
    EGame.BLACK_MYTH_WUKONG: PakFileVersion.Utf8PakDirectory,     # UE5.0+
    EGame.STALKER_2: PakFileVersion.Utf8PakDirectory,             # UE5.1
    EGame.MARVEL_RIVALS: PakFileVersion.Utf8PakDirectory,         # UE5.3
    EGame.THE_FIRST_DESCENDANT: PakFileVersion.Utf8PakDirectory,  # UE5.2
    EGame.INFINITY_NIKKI: PakFileVersion.Utf8PakDirectory,        # UE5.4
    EGame.WUTHERING_WAVES: PakFileVersion.Utf8PakDirectory,       # UE4.26
    EGame.DELTA_FORCE: PakFileVersion.Utf8PakDirectory,           # UE4.27
    EGame.SILENT_HILL_2_REMAKE: PakFileVersion.Utf8PakDirectory,  # UE5.1
    EGame.DUNE_AWAKENING: PakFileVersion.Utf8PakDirectory,        # UE5.2
    EGame.BORDERLANDS_4: PakFileVersion.Utf8PakDirectory,         # UE5.5
    EGame.GRAY_ZONE_WARFARE: PakFileVersion.Utf8PakDirectory,     # UE5.5
    # UE4 games
    EGame.PUBG: PakFileVersion.FNameBasedCompressionMethod,       # UE4.16
    EGame.FORTNITE: PakFileVersion.Utf8PakDirectory,              # UE4.20+
    EGame.APEX_LEGENDS: PakFileVersion.FNameBasedCompressionMethod, # UE4.23
    EGame.KINGDOM_HEARTS_3: PakFileVersion.FNameBasedCompressionMethod, # UE4.18
    EGame.FF7_REMAKE: PakFileVersion.FNameBasedCompressionMethod, # UE4.18
    EGame.GTA_TRILOGY: PakFileVersion.PathHashIndex,              # UE4.26
    EGame.HOGWARTS_LEGACY: PakFileVersion.PathHashIndex,          # UE4.27
    EGame.VALORANT: PakFileVersion.PathHashIndex,                 # UE4.27
    EGame.STATE_OF_DECAY_2: PakFileVersion.Initial,               # UE4.13
    EGame.DAYS_GONE: PakFileVersion.Initial,                      # UE4.11
    EGame.TEKKEN_7: PakFileVersion.Initial,                       # UE4.14
    EGame.BORDERLANDS_3: PakFileVersion.FNameBasedCompressionMethod, # UE4.20
}


# Magic to game identifier mapping
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
    """Detect game identifier from magic value.

    Args:
        magic: PAK file magic value

    Returns:
        Game identifier (EGame enum value)
    """
    return MAGIC_TO_GAME_MAP.get(magic, EGame.UNKNOWN)


def get_pak_version_for_game(game: int) -> int:
    """Get PAK file version for a game.

    Args:
        game: Game identifier (EGame enum value)

    Returns:
        PAK file version (PakFileVersion enum value)
    """
    return GAME_PAK_VERSION_MAP.get(game, PakFileVersion.Utf8PakDirectory)


def get_game_info(game: int) -> Tuple[str, int]:
    """Get game information."""
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
        EGame.BLACK_MYTH_WUKONG: "Black Myth: Wukong",
        EGame.STALKER_2: "S.T.A.L.K.E.R. 2",
        EGame.MARVEL_RIVALS: "Marvel Rivals",
        EGame.THE_FIRST_DESCENDANT: "The First Descendant",
        EGame.INFINITY_NIKKI: "Infinity Nikki",
        EGame.WUTHERING_WAVES: "Wuthering Waves",
        EGame.DELTA_FORCE: "Delta Force",
        EGame.SILENT_HILL_2_REMAKE: "Silent Hill 2 Remake",
        EGame.DUNE_AWAKENING: "Dune: Awakening",
        EGame.BORDERLANDS_4: "Borderlands 4",
        EGame.GRAY_ZONE_WARFARE: "Gray Zone Warfare",
        EGame.PUBG: "PUBG: Battlegrounds",
        EGame.FORTNITE: "Fortnite",
        EGame.APEX_LEGENDS: "Apex Legends",
        EGame.KINGDOM_HEARTS_3: "Kingdom Hearts III",
        EGame.FF7_REMAKE: "Final Fantasy VII Remake",
        EGame.GTA_TRILOGY: "GTA: The Trilogy",
        EGame.HOGWARTS_LEGACY: "Hogwarts Legacy",
        EGame.VALORANT: "VALORANT",
        EGame.STATE_OF_DECAY_2: "State of Decay 2",
        EGame.DAYS_GONE: "Days Gone",
        EGame.TEKKEN_7: "TEKKEN 7",
        EGame.BORDERLANDS_3: "Borderlands 3",
    }
    name = game_names.get(game, "Unknown")
    version = get_pak_version_for_game(game)
    return name, version
