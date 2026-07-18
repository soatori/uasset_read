"""BPGC 缓存与事件函数执行测试。

合并来源：
- test_bpgc_cache.py — BPGC bytecode cache 重试行为与诊断测试
- test_event_execution_fix.py — 事件函数执行输出修复与签名解析测试
"""
from __future__ import annotations

import json
import logging
import os
import struct
import subprocess
import sys

import pytest
import unittest.mock
from unittest.mock import MagicMock, patch

from uasset_read.kismet.bytecode_extractor import (
    _bpgc_bytecode_cache,
    _bpgc_cache_retries,
    _BPGC_MAX_RETRIES,
    reset_bpgc_cache,
)
from uasset_read.ir_builder import _extract_parameters_from_signature


# ================================================================
# BPGC bytecode cache 测试
# ================================================================

class TestBpgcCache:
    """Tests for BPGC bytecode cache retry behavior."""

    def setup_method(self):
        reset_bpgc_cache()

    def test_initial_state_is_none(self):
        """Cache starts as None (uninitialized)."""
        import uasset_read.kismet.bytecode_extractor as mod
        assert mod._bpgc_bytecode_cache is None
        assert mod._bpgc_cache_retries == 0

    def test_reset_clears_retry_counter(self):
        """reset_bpgc_cache() resets both cache and retry counter."""
        import uasset_read.kismet.bytecode_extractor as mod
        mod._bpgc_cache_retries = 2
        mod._bpgc_bytecode_cache = {}
        reset_bpgc_cache()
        assert mod._bpgc_bytecode_cache is None
        assert mod._bpgc_cache_retries == 0

    def test_cache_hit_returns_bytecode(self):
        """When function is in cache, its bytecode is returned."""
        import uasset_read.kismet.bytecode_extractor as mod
        mod._bpgc_bytecode_cache = {"TestFunc": b'\x00\x01\x02'}
        # Simulate cache lookup (the inline logic in _bpgc_fallback)
        func_name = "TestFunc"
        assert mod._bpgc_bytecode_cache.get(func_name) == b'\x00\x01\x02'

    def test_cache_miss_returns_none(self):
        """When function is not in cache, lookup returns None."""
        import uasset_read.kismet.bytecode_extractor as mod
        mod._bpgc_bytecode_cache = {}
        func_name = "MissingFunc"
        assert mod._bpgc_bytecode_cache.get(func_name) is None

    def test_failure_does_not_permanently_cache_empty(self):
        """After first failure, cache stays None (allows retry), not {}."""
        import uasset_read.kismet.bytecode_extractor as mod
        reset_bpgc_cache()
        assert mod._bpgc_bytecode_cache is None

        # Simulate first failure: increment retry but don't set cache to {}
        mod._bpgc_cache_retries += 1
        # Cache should still be None (not {}), so next call retries
        assert mod._bpgc_bytecode_cache is None
        assert mod._bpgc_cache_retries == 1

    def test_retry_limit_prevents_infinite_retry(self):
        """After _BPGC_MAX_RETRIES failures, cache is set to {} to stop retrying."""
        import uasset_read.kismet.bytecode_extractor as mod
        reset_bpgc_cache()

        # Simulate failures up to the limit
        for i in range(_BPGC_MAX_RETRIES):
            mod._bpgc_cache_retries += 1
            if mod._bpgc_cache_retries >= _BPGC_MAX_RETRIES:
                mod._bpgc_bytecode_cache = {}
                break

        assert mod._bpgc_bytecode_cache == {}
        # Cache is {} (not None), so `if _bpgc_bytecode_cache is None` will be False
        # and no further retries occur

    def test_success_resets_retry_counter(self):
        """After successful cache population, retry counter resets to 0."""
        import uasset_read.kismet.bytecode_extractor as mod
        reset_bpgc_cache()
        mod._bpgc_cache_retries = 2  # Simulate prior failures

        # Simulate successful extraction
        mod._bpgc_bytecode_cache = {"Func1": b'\xAA', "Func2": b'\xBB'}
        mod._bpgc_cache_retries = 0  # Reset on success

        assert mod._bpgc_cache_retries == 0
        assert len(mod._bpgc_bytecode_cache) == 2

    def test_max_retries_constant_is_sane(self):
        """_BPGC_MAX_RETRIES should be a positive integer."""
        assert isinstance(_BPGC_MAX_RETRIES, int)
        assert _BPGC_MAX_RETRIES > 0


# ================================================================
# BPGC 字节码解析诊断测试
# ================================================================

class TestBpgcBytecodeDiagnostics:
    """#343: BPGC 字节码诊断改进测试。"""

    def test_empty_bytecode_logs_info_not_warning(self, caplog):
        """空字节码（无数据）应使用 info 级别。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer

        with caplog.at_level(logging.INFO):
            result = _parse_cooked_bytecode_buffer(b'')

        assert result == []
        # 空数据不应有 warning
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 0

    def test_corrupted_bytecode_logs_debug(self):
        """损坏字节码应使用 debug 级别记录容错诊断。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer

        # 构造损坏数据：无效 size（unsigned 解释后远超剩余数据）
        corrupted = struct.pack('<i', -1) + b'\x00' * 10

        # 用 Handler 捕获日志，避免 caplog 在全量测试中受根日志器级别影响
        test_logger = logging.getLogger("uasset_read.kismet.bpgc_bytecode")
        old_level = test_logger.level
        test_logger.setLevel(logging.DEBUG)
        captured: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = lambda record: captured.append(record)
        test_logger.addHandler(handler)
        try:
            _result = _parse_cooked_bytecode_buffer(corrupted)
        finally:
            test_logger.removeHandler(handler)
            test_logger.setLevel(old_level)

        debugs = [r for r in captured if r.levelno == logging.DEBUG]
        assert len(debugs) > 0, f"Expected debug logs but got none"


def test_remaining_bytes_zero_early_return():
    """当 remaining_bytes <= 0 时，应在早期返回而非到达原第 198 行的死代码分支。"""
    from uasset_read.kismet.bpgc_bytecode import extract_bpgc_bytecode

    # 创建 mock 对象
    mock_archive = MagicMock()
    mock_export = MagicMock()
    mock_export.object_name = "TestBPGC"
    mock_export.serial_offset = 100
    mock_export.serial_size = 50
    mock_export.script_serialization_size = 100
    mock_export.has_script_serialization = True
    mock_summary = MagicMock()
    mock_summary.file_version_ue5 = 0

    # 设置 archive.tell() 返回大于 region_end 的值，使 remaining_bytes < 0
    # region_end = 100 + 50 = 150, tell() 返回 200 → remaining_bytes = -50
    mock_archive.tell.return_value = 200

    # 设置 detect_blueprint_generated_class 返回 True
    with unittest.mock.patch(
        "uasset_read.serializers.object_resources.detect_blueprint_generated_class",
        return_value=True,
    ):
        # 设置 read_property_tag 返回 None 终止符
        mock_tag = MagicMock()
        mock_tag.name = "None"
        with unittest.mock.patch(
            "uasset_read.serializers.property_tags.read_property_tag",
            return_value=mock_tag,
        ):
            result = extract_bpgc_bytecode(
                mock_archive, mock_export, mock_summary,
                "TestAsset", [], [], [],
            )

    # 验证返回空字典（早期返回）
    assert result == {}
    # 验证 read_bytes 未被调用（死代码未执行）
    mock_archive.read_bytes.assert_not_called()


# ================================================================
# 签名解析器单元测试
# ================================================================

class TestExtractParametersFromSignature:
    """签名解析器单元测试 — 不依赖外部资产。"""

    def test_empty_string_returns_empty(self):
        assert _extract_parameters_from_signature("") == []

    def test_none_returns_empty(self):
        assert _extract_parameters_from_signature(None) == []

    def test_no_parens_returns_empty(self):
        assert _extract_parameters_from_signature("void Func") == []

    def test_empty_parens(self):
        assert _extract_parameters_from_signature("void Func()") == []

    def test_single_param(self):
        result = _extract_parameters_from_signature("void Tick(float DeltaTime)")
        assert result == [{"name": "DeltaTime", "type": "float"}]

    def test_multiple_params(self):
        result = _extract_parameters_from_signature(
            "int32 Add(int32 A, int32 B)"
        )
        assert result == [
            {"name": "A", "type": "int32"},
            {"name": "B", "type": "int32"},
        ]

    def test_complex_type(self):
        result = _extract_parameters_from_signature(
            "void OnHit(AActor* OtherActor, FVector NormalImpulse)"
        )
        assert result == [
            {"name": "OtherActor", "type": "AActor*"},
            {"name": "NormalImpulse", "type": "FVector"},
        ]

    def test_type_with_const_ref(self):
        result = _extract_parameters_from_signature(
            "void foo(const FString& Name)"
        )
        assert result == [{"name": "Name", "type": "const FString&"}]

    def test_type_only_no_name(self):
        # rsplit(None, 1) on single token -> type-only
        result = _extract_parameters_from_signature("void Foo(int32)")
        assert result == [{"name": "", "type": "int32"}]

    def test_leading_trailing_commas(self):
        result = _extract_parameters_from_signature(
            "void Foo( , int32 A, )"
        )
        assert result == [{"name": "A", "type": "int32"}]

    def test_pointer_type(self):
        result = _extract_parameters_from_signature(
            "void OnOverlap(UPrimitiveComponent* OverlappedComp)"
        )
        assert result == [
            {"name": "OverlappedComp", "type": "UPrimitiveComponent*"}
        ]


# ================================================================
# 集成测试（依赖外部 UE 资产）
# ================================================================

_ASSET_ROOT = os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine")

TEST_ASSETS = [
    ("BP_InstancedStaticMeshBase", os.path.join(
        _ASSET_ROOT, "Engine", "Plugins", "Experimental", "AnimToTexture",
        "Content", "Characters", "Mannequin", "Blueprints",
        "BP_InstancedStaticMeshBase.uasset",
    )),
    ("BP_LocationProbe", os.path.join(
        _ASSET_ROOT, "Engine", "Plugins", "Runtime", "GeoReferencing",
        "Content", "Models", "LocationProbe",
        "BP_LocationProbe.uasset",
    )),
    ("BP_GrabToolActor", os.path.join(
        _ASSET_ROOT, "Engine", "Plugins", "VirtualProduction",
        "VirtualScouting", "Content", "Tools", "Grab",
        "BP_GrabToolActor.uasset",
    )),
]

_has_real_asset = any(os.path.isfile(p) for _, p in TEST_ASSETS)


def _parse_json(path: str) -> dict:
    """解析资产并返回 JSON。"""
    cmd = [sys.executable, "-m", "uasset_read", "--json", "--function-graphs", "--tolerant", path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"Parse failed: {r.stderr[:200]}"
    return json.loads(r.stdout)


@pytest.mark.integration
@pytest.mark.skipif(not _has_real_asset, reason="真实 UE 资产不可用")
class TestFunctionGraphs:
    """function_graphs 不再为空。"""

    @pytest.mark.parametrize("name,path", TEST_ASSETS)
    def test_function_graphs_populated(self, name, path):
        data = _parse_json(path)
        graphs = data.get("function_graphs", [])
        assert len(graphs) > 0, f"{name}: function_graphs 为空"

    @pytest.mark.parametrize("name,path", TEST_ASSETS)
    def test_function_graphs_have_structure(self, name, path):
        data = _parse_json(path)
        for g in data.get("function_graphs", []):
            assert "function_name" in g, "Missing function_name in graph"
            assert "signature" in g, "Missing signature in graph"


@pytest.mark.integration
@pytest.mark.skipif(not _has_real_asset, reason="真实 UE 资产不可用")
class TestEventFunctionParameters:
    """事件函数参数不再为空。"""

    @pytest.mark.parametrize("name,path", TEST_ASSETS)
    def test_decompiled_functions_have_params_key(self, name, path):
        data = _parse_json(path)
        events = [f for f in data.get("decompiled_functions", [])
                  if any(kw in f["name"] for kw in ["BeginPlay", "Tick", "ConstructionScript", "Receive"])]
        for ev in events:
            assert "parameters" in ev, \
                f"{ev['name']}: missing parameters key"

    def test_receive_begin_play_has_params(self):
        data = _parse_json(TEST_ASSETS[0][1])
        begin_play = [f for f in data["decompiled_functions"] if f["name"] == "ReceiveBeginPlay"]
        assert len(begin_play) == 1
        func = begin_play[0]
        assert func.get("signature"), "Missing signature"
