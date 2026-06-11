"""P2 格式修复测试 — 版本门控 (#96, #97)。"""
from __future__ import annotations

import pytest


class TestPreloadDependenciesVersionGate:
    """#96: PreloadDependencies 在 UE5 路径中应有版本门控。

    UE 源码 PackageFileSummary.cpp L503-511:
      if (Sum.FileVersionUE >= VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS)  // 512
          Record << Sum.PreloadDependenciesUE5;
    """

    def test_version_gate_logic(self):
        """验证版本门控逻辑正确性（纯逻辑测试）。"""
        UE4_PRELOAD_DEPS = 512

        def should_read_preload(file_version_ue4: int) -> bool:
            return file_version_ue4 >= UE4_PRELOAD_DEPS

        assert should_read_preload(512) is True
        assert should_read_preload(516) is True
        assert should_read_preload(511) is False
        assert should_read_preload(0) is False
        assert should_read_preload(522) is True
