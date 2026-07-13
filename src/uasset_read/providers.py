"""
GameDirectoryProvider — 游戏目录自动扫描提供者。

扫描指定根目录下的游戏资产文件，支持按扩展名过滤和模式匹配。
"""

import fnmatch
import os
from pathlib import Path
from typing import List, Optional


# 支持的资产扩展名
UE_ASSET_EXTENSIONS = (".uasset", ".umap")
UE_PAK_EXTENSIONS = (".upak",)
UE_UTOC_EXTENSIONS = (".utoc",)


class GameDirectoryProvider:
    """
    游戏目录自动扫描提供者。

    扫描指定根目录，检测 .uproject 文件，
    并列出指定扩展名的游戏资产文件。

    Parameters
    ----------
    root_dir : str | Path
        游戏项目根目录路径。

    Raises
    ------
    FileNotFoundError
        如果 root_dir 不存在或不是一个目录。
    """

    def __init__(self, root_dir: str | Path) -> None:
        self._root = Path(root_dir).resolve()
        if not self._root.exists():
            raise FileNotFoundError(f"目录不存在: {self._root}")
        if not self._root.is_dir():
            raise NotADirectoryError(f"路径不是目录: {self._root}")
        self._list_files_cache: dict[str, list[Path]] = {}

    @property
    def root(self) -> Path:
        """返回解析后的根目录路径。"""
        return self._root

    def has_uproject(self) -> bool:
        """
        检测根目录下是否存在 .uproject 文件。

        Returns
        -------
        bool
            如果存在至少一个 .uproject 文件则返回 True。
        """
        return any(self._root.glob("*.uproject"))

    def get_uproject_file(self) -> Optional[Path]:
        """
        获取根目录下的第一个 .uproject 文件。

        Returns
        -------
        Optional[Path]
            .uproject 文件路径，不存在则返回 None。
        """
        for f in self._root.glob("*.uproject"):
            return f
        return None

    def list_files(self, extension: str) -> List[Path]:
        """
        列出指定扩展名的所有文件（递归扫描，带缓存）。

        Parameters
        ----------
        extension : str
            文件扩展名，如 ".uasset"、".pak"。带或不带前导点均可。

        Returns
        -------
        List[Path]
            匹配的文件路径列表，按字母顺序排序。
        """
        ext = extension if extension.startswith(".") else f".{extension}"
        ext_lower = ext.lower()
        if ext_lower in self._list_files_cache:
            return self._list_files_cache[ext_lower]
        results: List[Path] = []
        for dirpath, _, filenames in os.walk(self._root):
            for fn in filenames:
                if fn.lower().endswith(ext_lower):
                    results.append(Path(dirpath) / fn)
        sorted_results = sorted(results)
        self._list_files_cache[ext_lower] = sorted_results
        return sorted_results

    def refresh_file_cache(self) -> None:
        """清除文件列表缓存，下次 list_files() 调用时重新扫描。"""
        self._list_files_cache.clear()

    def list_uasset_files(self) -> List[Path]:
        """
        列出所有 .uasset 和 .umap 文件。

        Returns
        -------
        List[Path]
            资产文件路径列表。
        """
        results: List[Path] = []
        for ext in UE_ASSET_EXTENSIONS:
            results.extend(self.list_files(ext))
        return sorted(results)

    def list_pak_files(self) -> List[Path]:
        """
        列出所有 .upak 文件。

        Returns
        -------
        List[Path]
            PAK 文件路径列表。
        """
        results: List[Path] = []
        for ext in UE_PAK_EXTENSIONS:
            results.extend(self.list_files(ext))
        return sorted(results)

    def list_utoc_files(self) -> List[Path]:
        """
        列出所有 .utoc 文件。

        Returns
        -------
        List[Path]
            UToc 文件路径列表。
        """
        results: List[Path] = []
        for ext in UE_UTOC_EXTENSIONS:
            results.extend(self.list_files(ext))
        return sorted(results)

    def find_file(self, pattern: str) -> List[Path]:
        """
        使用 fnmatch 模式匹配文件名。

        Parameters
        ----------
        pattern : str
            匹配模式（支持 *, ?, [seq] 等 shell 通配符）。

        Returns
        -------
        List[Path]
            匹配的文件路径列表，按字母顺序排序。
        """
        results: List[Path] = []
        for dirpath, _, filenames in os.walk(self._root):
            for fn in filenames:
                if fnmatch.fnmatch(fn, pattern):
                    results.append(Path(dirpath) / fn)
        return sorted(results)
