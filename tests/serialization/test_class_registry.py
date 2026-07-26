"""Class registry bootstrap and handler lookup tests.

Verifies that get_class_registry() triggers automatic handler registration
even when asset_types module has not been explicitly imported.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from uasset_read.parsers.class_registry import (
    get_class_registry,
    reset_class_registry,
)


class TestRegistryBootstrap:
    """Test automatic handler registration on first get_class_registry() call."""

    def setup_method(self) -> None:
        """Reset registry before each test to ensure clean state."""
        reset_class_registry()

    def test_bootstrap_populates_registry(self) -> None:
        """get_class_registry() should register handlers even without prior asset_types import."""
        registry = get_class_registry()
        handlers = registry.get_registered_handlers()
        assert len(handlers) > 0, "Registry should have registered handlers after bootstrap"

    def test_sound_attenuation_handler_available(self) -> None:
        """SoundAttenuation handler should be findable without importing asset_types."""
        registry = get_class_registry()
        handler = registry.find_handler("SoundAttenuation")
        assert handler is not None, "SoundAttenuation handler should be registered"
        assert handler.handler_name == "SoundAttenuationHandler"

    def test_animation_data_model_handler_available(self) -> None:
        """AnimationDataModel handler should be findable without importing asset_types."""
        registry = get_class_registry()
        handler = registry.find_handler("AnimationDataModel")
        assert handler is not None, "AnimationDataModel handler should be registered"
        assert handler.handler_name == "AnimDataModelHandler"

    def test_static_mesh_handler_available(self) -> None:
        """StaticMesh handler should be findable without importing asset_types."""
        registry = get_class_registry()
        handler = registry.find_handler("StaticMesh")
        assert handler is not None, "StaticMesh handler should be registered"
        assert handler.handler_name == "StaticMeshHandler"

    def test_unknown_class_returns_none(self) -> None:
        """find_handler for unknown class should return None."""
        registry = get_class_registry()
        handler = registry.find_handler("NonExistentClass")
        assert handler is None

    def test_bootstrap_called_only_once(self) -> None:
        """Multiple get_class_registry() calls should not re-register handlers."""
        registry1 = get_class_registry()
        count1 = len(registry1.get_registered_handlers())
        registry2 = get_class_registry()
        count2 = len(registry2.get_registered_handlers())
        assert count1 == count2, "Handler count should be stable across calls"
        assert count1 > 0

    def test_reset_allows_re_bootstrap(self) -> None:
        """reset_class_registry() should allow fresh bootstrap."""
        registry = get_class_registry()
        count_before = len(registry.get_registered_handlers())
        reset_class_registry()
        registry2 = get_class_registry()
        count_after = len(registry2.get_registered_handlers())
        assert count_before == count_after


class TestIsolatedProcess:
    """Test that registry works in a fresh Python process without asset_types import."""

    def test_registry_in_subprocess(self) -> None:
        """Registry should work when invoked in a fresh process."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from uasset_read.parsers.class_registry import get_class_registry; "
                "r = get_class_registry(); "
                "h = r.find_handler('SoundAttenuation'); "
                "assert h is not None, 'SoundAttenuation handler not found'; "
                "assert h.handler_name == 'SoundAttenuationHandler'; "
                "print('OK')",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "OK" in result.stdout
