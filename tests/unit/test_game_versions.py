"""游戏版本映射测试"""
import unittest

from uasset_read.pak.game_versions import (
    EGame,
    GAME_PAK_VERSION_MAP,
    MAGIC_TO_GAME_MAP,
    detect_game_from_magic,
    get_pak_version_for_game,
    get_game_info,
)
from uasset_read.pak.constants import PakFileVersion


class TestEGameExpansion(unittest.TestCase):
    """EGame 枚举扩展测试"""

    def test_popular_ue5_games_exist(self):
        """EGame 应包含热门 UE5 游戏"""
        self.assertTrue(hasattr(EGame, "BLACK_MYTH_WUKONG"))
        self.assertTrue(hasattr(EGame, "STALKER_2"))
        self.assertTrue(hasattr(EGame, "MARVEL_RIVALS"))
        self.assertTrue(hasattr(EGame, "THE_FIRST_DESCENDANT"))
        self.assertTrue(hasattr(EGame, "INFINITY_NIKKI"))

    def test_popular_ue4_games_exist(self):
        """EGame 应包含热门 UE4 游戏"""
        self.assertTrue(hasattr(EGame, "PUBG"))
        self.assertTrue(hasattr(EGame, "FORTNITE"))
        self.assertTrue(hasattr(EGame, "APEX_LEGENDS"))

    def test_game_pak_version_mapping(self):
        """新增游戏应有 PAK 版本映射"""
        self.assertIn(EGame.BLACK_MYTH_WUKONG, GAME_PAK_VERSION_MAP)
        self.assertEqual(
            GAME_PAK_VERSION_MAP[EGame.BLACK_MYTH_WUKONG],
            PakFileVersion.Utf8PakDirectory,
        )

    def test_game_info_returns_name(self):
        """get_game_info 应返回正确游戏名称"""
        name, version = get_game_info(EGame.BLACK_MYTH_WUKONG)
        self.assertEqual(name, "Black Myth: Wukong")

    def test_custom_magic_games_unchanged(self):
        """自定义魔数游戏应保持原有映射"""
        self.assertEqual(
            detect_game_from_magic(0xA590ED1E), EGame.OUTLAST_TRIALS
        )
        self.assertEqual(
            get_pak_version_for_game(EGame.OUTLAST_TRIALS),
            PakFileVersion.PathHashIndex,
        )


if __name__ == "__main__":
    unittest.main()
