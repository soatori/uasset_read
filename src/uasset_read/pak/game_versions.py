"""
Game version mapping -- infer PAK file version from game identifier.

Reference: external/CUE4Parse/CUE4Parse/UE4/Versions/EGame.cs implementation.
"""

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

