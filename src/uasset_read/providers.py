"""
GameDirectoryProvider — game directory auto-scan provider.

Scans game asset files under a specified root directory, with extension filtering and pattern matching.
"""

import fnmatch
import os
from pathlib import Path
from typing import List, Optional


# Supported asset extensions
UE_ASSET_EXTENSIONS = (".uasset", ".umap")
UE_PAK_EXTENSIONS = (".upak",)
UE_UTOC_EXTENSIONS = (".utoc",)


class GameDirectoryProvider:
    """
    Game directory auto-scan provider.

    Scans the specified root directory, detects .uproject files,
    and lists game asset files with specified extensions.

    Parameters
    ----------
    root_dir : str | Path
        Game project root directory path.

    Raises
    ------
    FileNotFoundError
        If root_dir does not exist or is not a directory.
    """

    def __init__(self, root_dir: str | Path) -> None:
        self._root = Path(root_dir).resolve()
        if not self._root.exists():
            raise FileNotFoundError(f"Directory does not exist: {self._root}")
        if not self._root.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self._root}")
        self._list_files_cache: dict[str, list[Path]] = {}

    @property
    def root(self) -> Path:
        """Returns the resolved root directory path."""
        return self._root

    def has_uproject(self) -> bool:
        """
        Check if a .uproject file exists in the root directory.

        Returns
        -------
        bool
            True if at least one .uproject file exists.
        """
        return any(self._root.glob("*.uproject"))

    def get_uproject_file(self) -> Optional[Path]:
        """
        Get the first .uproject file in the root directory.

        Returns
        -------
        Optional[Path]
            .uproject file path, or None if not found.
        """
        for f in self._root.glob("*.uproject"):
            return f
        return None

    def list_files(self, extension: str) -> List[Path]:
        """
        List all files with a given extension (recursive scan, cached).

        Parameters
        ----------
        extension : str
            File extension, e.g. ".uasset", ".pak". With or without leading dot.

        Returns
        -------
        List[Path]
            Matching file paths, sorted alphabetically.
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
        """Clear the file list cache; next list_files() call will rescan."""
        self._list_files_cache.clear()

    def list_uasset_files(self) -> List[Path]:
        """
        List all .uasset and .umap files.

        Returns
        -------
        List[Path]
            Asset file paths.
        """
        results: List[Path] = []
        for ext in UE_ASSET_EXTENSIONS:
            results.extend(self.list_files(ext))
        return sorted(results)

    def list_pak_files(self) -> List[Path]:
        """
        List all .upak files.

        Returns
        -------
        List[Path]
            PAK file paths.
        """
        results: List[Path] = []
        for ext in UE_PAK_EXTENSIONS:
            results.extend(self.list_files(ext))
        return sorted(results)

    def list_utoc_files(self) -> List[Path]:
        """
        List all .utoc files.

        Returns
        -------
        List[Path]
            UToc file paths.
        """
        results: List[Path] = []
        for ext in UE_UTOC_EXTENSIONS:
            results.extend(self.list_files(ext))
        return sorted(results)

    def find_file(self, pattern: str) -> List[Path]:
        """
        Match filenames using fnmatch pattern.

        Parameters
        ----------
        pattern : str
            Match pattern (supports *, ?, [seq] and other shell wildcards).

        Returns
        -------
        List[Path]
            Matching file paths, sorted alphabetically.
        """
        results: List[Path] = []
        for dirpath, _, filenames in os.walk(self._root):
            for fn in filenames:
                if fnmatch.fnmatch(fn, pattern):
                    results.append(Path(dirpath) / fn)
        return sorted(results)
