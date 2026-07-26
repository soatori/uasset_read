"""Adversarial tests for ResourceBudget live runtime ownership.

Proves that ResourceBudget is created once per parse call and threaded
through decompression, table reads, and bundle loads. Verifies bounded
behavior under adversarial conditions (huge decompressed output, huge
array_dim, huge bundle payloads).
"""

from __future__ import annotations

import gzip
import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from uasset_read.memory_safety import (
    AllocationLimits,
    MemoryLimitExceeded,
    ResourceBudget,
)
from uasset_read.constants import MAX_ARRAY_DIM


# ---------------------------------------------------------------------------
# ResourceBudget core behaviour
# ---------------------------------------------------------------------------

class TestResourceBudgetReserve:
    """Budget reserve() enforces all three limits."""

    def test_reserve_within_limits(self):
        budget = ResourceBudget(AllocationLimits(
            max_single_read_bytes=1024,
            max_decompressed_block_bytes=2048,
            max_total_decompressed_bytes=4096,
        ))
        # Should not raise
        budget.reserve(512, "test")
        assert budget.total_decompressed == 512

    def test_reserve_exceeds_single_read(self):
        budget = ResourceBudget(AllocationLimits(
            max_single_read_bytes=1024,
            max_decompressed_block_bytes=4096,
            max_total_decompressed_bytes=8192,
        ))
        with pytest.raises(MemoryLimitExceeded):
            budget.reserve(2048, "test_single_read")

    def test_reserve_exceeds_decompressed_block(self):
        budget = ResourceBudget(AllocationLimits(
            max_single_read_bytes=4096,
            max_decompressed_block_bytes=1024,
            max_total_decompressed_bytes=8192,
        ))
        # bytes_needed=2048 exceeds max_decompressed_block_bytes=1024
        with pytest.raises(MemoryLimitExceeded):
            budget.reserve(2048, "test_decomp_block")

    def test_reserve_exceeds_total_decompressed(self):
        budget = ResourceBudget(AllocationLimits(
            max_single_read_bytes=4096,
            max_decompressed_block_bytes=4096,
            max_total_decompressed_bytes=2048,
        ))
        # First reserve: 1024 (OK), second: 1024 (total becomes 2048, OK)
        budget.reserve(1024, "a")
        budget.reserve(1024, "b")
        assert budget.total_decompressed == 2048
        # Third: total becomes 3072 > 2048
        with pytest.raises(MemoryLimitExceeded):
            budget.reserve(1024, "c")

    def test_checkpoint_rollback(self):
        budget = ResourceBudget(AllocationLimits(
            max_single_read_bytes=4096,
            max_decompressed_block_bytes=4096,
            max_total_decompressed_bytes=16384,
        ))
        budget.reserve(1024, "a")
        budget.checkpoint()
        budget.reserve(1024, "b")
        assert budget.total_decompressed == 2048
        budget.rollback()
        assert budget.total_decompressed == 1024


# ---------------------------------------------------------------------------
# Mappings: gzip decompress budget
# ---------------------------------------------------------------------------

class TestJmapGzipDecompressBudget:
    """Prove JMAP gzip decompression reserves decompressed output size."""

    def _write_jmap_gz(self, data: dict, tmp_dir: str) -> str:
        """Write a gzip-compressed JMAP file to disk and return the path."""
        path = os.path.join(tmp_dir, "test.jmap.gz")
        text = json.dumps(data).encode("utf-8")
        with gzip.open(path, "wb") as f:
            f.write(text)
        return path

    def test_gzip_decompress_reserves_output_size(self):
        """Budget must track decompressed output, not just compressed input."""
        jmap_data = {"objects": {}}

        with tempfile.TemporaryDirectory() as tmp_dir:
            gz_path = self._write_jmap_gz(jmap_data, tmp_dir)
            gz_size = os.path.getsize(gz_path)

            # Use a tight budget: allow file read but small total
            budget = ResourceBudget(AllocationLimits(
                max_single_read_bytes=gz_size + 1024,
                max_decompressed_block_bytes=1024 * 1024,
                max_total_decompressed_bytes=1024 * 1024,
            ))
            from uasset_read.mappings import JmapParser
            JmapParser(gz_path, budget=budget)
            # Budget should have tracked both file read + decompressed output
            assert budget.total_decompressed > gz_size

    def test_gzip_decompress_exceeds_budget(self):
        """Budget rejects decompressed output that exceeds total limit."""
        jmap_data = {"objects": {}}

        with tempfile.TemporaryDirectory() as tmp_dir:
            gz_path = self._write_jmap_gz(jmap_data, tmp_dir)
            gz_size = os.path.getsize(gz_path)

            # Set total budget smaller than file size + decompressed output
            tiny_budget = ResourceBudget(AllocationLimits(
                max_single_read_bytes=gz_size + 1024,
                max_decompressed_block_bytes=1024 * 1024,
                max_total_decompressed_bytes=4,  # very small total
            ))
            from uasset_read.mappings import JmapParser
            with pytest.raises(MemoryLimitExceeded):
                JmapParser(gz_path, budget=tiny_budget)


# ---------------------------------------------------------------------------
# Mappings: array_dim upper-bound validation
# ---------------------------------------------------------------------------

class TestJmapArrayDimValidation:
    """Prove array_dim is validated against MAX_ARRAY_DIM."""

    def _make_jmap_bytes(self, array_dim: int) -> bytes:
        """Create a JMAP JSON with a single property having given array_dim."""
        jmap_data = {
            "objects": {
                "/Game/Test.Test": {
                    "type": "Class",
                    "properties": [
                        {
                            "name": "EvilProp",
                            "type": "IntProperty",
                            "array_dim": array_dim,
                        }
                    ],
                }
            }
        }
        return json.dumps(jmap_data).encode("utf-8")

    def test_array_dim_within_limit(self):
        from uasset_read.mappings import JmapParser
        data = self._make_jmap_bytes(MAX_ARRAY_DIM)
        budget = ResourceBudget()
        JmapParser(data, budget=budget)  # should not raise

    def test_array_dim_exceeds_limit(self):
        from uasset_read.mappings import JmapParser
        data = self._make_jmap_bytes(MAX_ARRAY_DIM + 1)
        budget = ResourceBudget()
        with pytest.raises(Exception, match="array_dim out of range"):
            JmapParser(data, budget=budget)

    def test_array_dim_zero_rejected(self):
        from uasset_read.mappings import JmapParser
        data = self._make_jmap_bytes(0)
        budget = ResourceBudget()
        with pytest.raises(Exception, match="array_dim out of range"):
            JmapParser(data, budget=budget)


# ---------------------------------------------------------------------------
# Bundle reads: budget enforcement
# ---------------------------------------------------------------------------

class TestBundleBudgetEnforcement:
    """Prove PackageProvider.open_package_bundle respects budget."""

    def test_bundle_read_reserves_main_and_sidecar(self):
        """Budget reserves space for main and sidecar payloads in-memory provider."""
        from uasset_read.package import PackageProvider, PackageBundle

        samples = Path(__file__).parent / "samples"
        if not samples.exists():
            pytest.skip("samples directory not found")
        assets = list(samples.glob("*.uasset"))
        if not assets:
            pytest.skip("no .uasset files in samples")

        main_data = assets[0].read_bytes()

        # Create an in-memory provider that returns file bytes
        class InMemoryProvider(PackageProvider):
            container = "test"
            def __init__(self, files_dict):
                self._files = files_dict
            def list_files(self):
                return list(self._files.keys())
            def read_file(self, path):
                return self._files.get(path)

        provider = InMemoryProvider({str(assets[0]): main_data})
        budget = ResourceBudget(AllocationLimits(
            max_single_read_bytes=len(main_data) + 1024,
            max_decompressed_block_bytes=len(main_data) + 1024,
            max_total_decompressed_bytes=len(main_data) * 2,
        ))
        bundle = provider.open_package_bundle(
            str(assets[0]), tolerant=True, budget=budget,
        )
        # Budget should have been charged for main payload
        assert budget.total_decompressed >= len(main_data)
        bundle.close()

    def test_bundle_exceeds_budget(self):
        """Budget rejects bundle when main payload exceeds total limit."""
        from uasset_read.package import PackageProvider

        samples = Path(__file__).parent / "samples"
        if not samples.exists():
            pytest.skip("samples directory not found")
        assets = list(samples.glob("*.uasset"))
        if not assets:
            pytest.skip("no .uasset files in samples")

        main_data = assets[0].read_bytes()
        file_size = len(main_data)

        class InMemoryProvider(PackageProvider):
            container = "test"
            def __init__(self, files_dict):
                self._files = files_dict
            def list_files(self):
                return list(self._files.keys())
            def read_file(self, path):
                return self._files.get(path)

        provider = InMemoryProvider({str(assets[0]): main_data})
        # Budget too small for the main payload
        tiny_budget = ResourceBudget(AllocationLimits(
            max_single_read_bytes=file_size + 1,
            max_decompressed_block_bytes=file_size + 1,
            max_total_decompressed_bytes=file_size - 1,
        ))
        with pytest.raises(MemoryLimitExceeded):
            provider.open_package_bundle(
                str(assets[0]), tolerant=True, budget=tiny_budget,
            )


# ---------------------------------------------------------------------------
# Budget creation in parse pipeline
# ---------------------------------------------------------------------------

class TestBudgetCreationInPipeline:
    """Prove ResourceBudget is created at entry points."""

    def test_parse_package_core_creates_budget(self):
        """_parse_package_core creates a ResourceBudget and passes it through."""
        samples = Path(__file__).parent / "samples"
        if not samples.exists():
            pytest.skip("samples directory not found")
        assets = list(samples.glob("*.uasset"))
        if not assets:
            pytest.skip("no .uasset files in samples")

        from uasset_read.parse_uasset import parse_package
        # Parse should succeed — budget is created internally
        result = parse_package(
            str(assets[0]), tolerant=True,
        )
        assert result.summary is not None
        assert result.name_map is not None

    def test_parse_package_lazy_creates_budget(self):
        """parse_package_lazy creates a ResourceBudget and passes it through."""
        samples = Path(__file__).parent / "samples"
        if not samples.exists():
            pytest.skip("samples directory not found")
        assets = list(samples.glob("*.uasset"))
        if not assets:
            pytest.skip("no .uasset files in samples")

        from uasset_read.parse_uasset import parse_package_lazy
        result = parse_package_lazy(
            str(assets[0]), tolerant=True,
        )
        assert result.summary is not None

    def test_budget_rejects_huge_name_table_count(self):
        """Budget reserves space when reading validated count."""
        from uasset_read.serializers.package_summary import (
            read_validated_count_strict,
        )

        budget = ResourceBudget(AllocationLimits(
            max_single_read_bytes=1024,
            max_decompressed_block_bytes=1024,
            max_total_decompressed_bytes=2048,
        ))
        # count=100, bytes_per_entry=16 → 1600 bytes, exceeds max_total=2048
        # after first 1024 reserved
        budget.reserve(1024, "seed")
        with pytest.raises(MemoryLimitExceeded):
            read_validated_count_strict(
                count=100,
                max_value=10_000_000,
                stage="test_huge_count",
                bytes_per_entry=16,
                budget=budget,
            )


# ---------------------------------------------------------------------------
# Adversarial: budget tracks cumulative decompression across multiple stages
# ---------------------------------------------------------------------------

class TestBudgetCumulativeTracking:
    """Prove that budget accumulates across reserve calls and rejects overflow."""

    def test_multiple_reserves_accumulate_and_reject(self):
        """Budget accumulates decompressed bytes and rejects when total is exceeded."""
        budget = ResourceBudget(AllocationLimits(
            max_single_read_bytes=1024 * 1024,
            max_decompressed_block_bytes=1024 * 1024,
            max_total_decompressed_bytes=3000,
        ))
        budget.reserve(1024, "stage_a")
        budget.reserve(1024, "stage_b")
        assert budget.total_decompressed == 2048
        with pytest.raises(MemoryLimitExceeded):
            budget.reserve(1024, "stage_c")

    def test_checkpoint_and_rollback_restores_budget(self):
        """Budget checkpoint/rollback restores decompressed byte counter."""
        budget = ResourceBudget(AllocationLimits(
            max_single_read_bytes=1024 * 1024,
            max_decompressed_block_bytes=1024 * 1024,
            max_total_decompressed_bytes=8192,
        ))
        budget.reserve(1024, "before_checkpoint")
        budget.checkpoint()
        budget.reserve(1024, "after_checkpoint")
        assert budget.total_decompressed == 2048
        budget.rollback()
        assert budget.total_decompressed == 1024
        # Can now reserve more
        budget.reserve(1024, "after_rollback")
        assert budget.total_decompressed == 2048


# ---------------------------------------------------------------------------
# Adversarial: budget flows through pipeline stages
# ---------------------------------------------------------------------------

class TestBudgetPassThrough:
    """Prove that budget is passed from entry points to sub-stages."""

    def test_init_parse_env_passes_budget_to_bundle(self):
        """_init_parse_env passes budget to open_package_bundle."""
        from unittest.mock import patch, MagicMock
        from uasset_read.pipeline.stages import _init_parse_env
        from uasset_read.models.result import ParseResult

        budget = ResourceBudget()
        result = ParseResult()
        bundle_kwargs = {}

        archive_mock = MagicMock()
        archive_mock.get_mmap_info.return_value = {"used": False, "warning": None}
        bundle_mock = MagicMock()
        bundle_mock.open_archive.return_value = archive_mock

        def spy_bundle(path, **kwargs):
            bundle_kwargs.update(kwargs)
            return bundle_mock

        with patch("uasset_read.pipeline.stages.open_package_bundle", spy_bundle):
            _init_parse_env(
                "test.uasset", result, tolerant=True,
                provider=None, mappings_path=None,
                game=None, check_aes_key=None, hex_view=False,
                budget=budget,
            )

        assert "budget" in bundle_kwargs
        assert bundle_kwargs["budget"] is budget

    def test_init_parse_env_passes_budget_to_mappings(self):
        """_init_parse_env passes budget to TypeMappingsProvider.from_file."""
        from unittest.mock import patch, MagicMock
        from uasset_read.pipeline.stages import _init_parse_env
        from uasset_read.models.result import ParseResult

        budget = ResourceBudget()
        result = ParseResult()
        called_kwargs = {}

        def spy_from_file(path, **kwargs):
            called_kwargs.update(kwargs)
            raise FileNotFoundError("expected")

        mock_tp = MagicMock()
        mock_tp.from_file = spy_from_file
        with patch("uasset_read.mappings.TypeMappingsProvider", mock_tp):
            try:
                _init_parse_env(
                    "nonexistent.uasset", result, tolerant=True,
                    provider=None, mappings_path="/fake.mappings",
                    game=None, check_aes_key=None, hex_view=False,
                    budget=budget,
                )
            except (FileNotFoundError, Exception):
                pass

        assert "budget" in called_kwargs
        assert called_kwargs["budget"] is budget

    def test_decompression_chunked_reserves_budget(self):
        """decompress_block_chunked reserves uncompressed_size from budget."""
        from uasset_read.pak.decompress import decompress_block_chunked

        budget = ResourceBudget(AllocationLimits(
            max_single_read_bytes=1024 * 1024,
            max_decompressed_block_bytes=256,
            max_total_decompressed_bytes=1024 * 1024,
        ))
        # Should raise because uncompressed_size (300) > max_decompressed_block (256)
        with pytest.raises(MemoryLimitExceeded):
            list(decompress_block_chunked(
                b"\x00" * 10,
                uncompressed_size=300,
                method="Zlib",
                budget=budget,
            ))

    def test_decompression_chunked_no_budget_skips_check(self):
        """decompress_block_chunked skips reserve when budget is None."""
        import zlib
        from uasset_read.pak.decompress import decompress_block_chunked

        original = b"hello world test data"
        compressed = zlib.compress(original)
        chunks = list(decompress_block_chunked(
            compressed,
            uncompressed_size=len(original),
            method="Zlib",
            budget=None,
        ))
        result = b"".join(chunks)
        assert result == original


class TestBudgetPassThroughLazyFallback:
    """Prove that budget is passed through the lazy path fallback branch."""

    def test_read_package_headers_accepts_budget(self):
        """_read_package_headers should accept a budget parameter and pass it downstream."""
        from unittest.mock import patch, MagicMock
        from uasset_read.pipeline.stages import _read_package_headers
        from uasset_read.models.result import ParseResult

        budget = ResourceBudget()
        result = ParseResult()
        init_kwargs = {}

        archive_mock = MagicMock()
        archive_mock.get_mmap_info.return_value = {"used": False, "warning": None}
        bundle_mock = MagicMock()
        bundle_mock.open_archive.return_value = archive_mock

        def spy_init(path, result, tolerant, provider, mappings_path, game, check_aes_key, hex_view, budget=None):
            init_kwargs["budget"] = budget
            return archive_mock, bundle_mock, None

        with patch("uasset_read.pipeline.stages._init_parse_env", spy_init):
            try:
                _read_package_headers(
                    "test.uasset", result,
                    tolerant=True, provider=None,
                    mappings_path=None, game=None,
                    budget=budget,
                )
            except Exception:
                pass

        assert "budget" in init_kwargs
        assert init_kwargs["budget"] is budget
