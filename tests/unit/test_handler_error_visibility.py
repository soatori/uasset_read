"""Tests proving that asset-type handler errors are visible to callers.

Task #479: Handler failures must be reported through the HandlerResult
contract and propagated to the export's parse_status, not silently swallowed.
"""
import logging
import struct
from unittest.mock import MagicMock

import pytest

from uasset_read.parsers.class_registry import (
    ClassHandler,
    ClassHandlerRegistry,
    FallbackPolicy,
    HandlerResult,
    get_class_registry,
    reset_class_registry,
)
from uasset_read.parsers.asset_types import (
    AssetTypeHandler,
    HandlerClassAdapter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FailingHandler(ClassHandler):
    """A handler that always raises ValueError."""

    def can_handle(self, class_name: str) -> bool:
        return class_name == "FailingClass"

    @property
    def handler_name(self) -> str:
        return "FailingHandler"

    def parse(self, export, archive, context=None):
        raise ValueError("deliberate parse failure")


class _FailingHandlerViaResult(ClassHandler):
    """A handler that returns HandlerResult(success=False)."""

    def can_handle(self, class_name: str) -> bool:
        return class_name == "FailingResultClass"

    @property
    def handler_name(self) -> str:
        return "FailingResultHandler"

    def parse(self, export, archive, context=None):
        return HandlerResult(
            success=False,
            error_message="handler chose to report failure",
            fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
        )


class _SuccessHandler(ClassHandler):
    """A handler that succeeds."""

    def can_handle(self, class_name: str) -> bool:
        return class_name == "SuccessClass"

    @property
    def handler_name(self) -> str:
        return "SuccessHandler"

    def parse(self, export, archive, context=None):
        return HandlerResult(
            success=True,
            data={"parse_status": "success", "key": "value"},
            fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
        )


class _MockHandlerForAdapter:
    """Handler with handle() method for HandlerClassAdapter testing."""

    def handle(self, export, context):
        raise ValueError("adapter test failure")


class _MockHandlerForAdapterStructError:
    """Handler with handle() method that raises struct.error."""

    def handle(self, export, context):
        raise struct.error("buffer too short")


class _MockHandlerForAdapterSuccess:
    """Handler with handle() method that succeeds."""

    def handle(self, export, context):
        from uasset_read.models.fallback import ExportParseStatus
        return ExportParseStatus.SUCCESS


class _MockHandlerForAdapterPartial:
    """Handler with handle() method that returns partial status."""

    def handle(self, export, context):
        from uasset_read.models.fallback import ExportParseStatus
        return ExportParseStatus.PARTIAL


class _MockHandlerForAdapterRaisesUnexpected:
    """Handler with handle() method that raises KeyError (not in adapter's catch list)."""

    def handle(self, export, context):
        raise KeyError("unexpected key")


def _make_export(class_name: str = "FailingClass"):
    """Create a minimal mock export that tracks setattr calls."""
    export = MagicMock()
    export.object_name = "TestExport"
    export.class_index = MagicMock()
    export.properties = []
    return export


def _make_archive(data: bytes = b""):
    """Create a mock FArchive for testing."""
    archive = MagicMock()
    archive.tell.return_value = 0
    archive.total_size.return_value = len(data)
    archive.read.return_value = data
    return archive


# ---------------------------------------------------------------------------
# HandlerResult contract tests
# ---------------------------------------------------------------------------

class TestHandlerResultContract:
    """Verify that HandlerResult carries error information."""

    def test_failed_handler_result_has_error_message(self):
        """HandlerResult(success=False) should carry error_message."""
        result = HandlerResult(
            success=False,
            error_message="something went wrong",
        )
        assert result.success is False
        assert result.error_message == "something went wrong"

    def test_successful_handler_result_has_no_error(self):
        """HandlerResult(success=True) should have None error_message."""
        result = HandlerResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.error_message is None


# ---------------------------------------------------------------------------
# AssetTypeHandler error propagation
# ---------------------------------------------------------------------------

class TestAssetTypeHandlerErrorVisibility:
    """AssetTypeHandler.parse() must return HandlerResult(success=False) on failure."""

    def test_parse_returns_failed_result_on_exception(self):
        """When parse_func raises, HandlerResult(success=False) is returned."""
        def _bad_parse(archive, name_map):
            raise ValueError("corrupt data")

        handler = AssetTypeHandler(
            class_names=["BadClass"],
            parse_func=_bad_parse,
            handler_name="BadHandler",
        )
        export = _make_export()
        archive = _make_archive()

        result = handler.parse(export, archive)

        assert result.success is False
        assert "corrupt data" in result.error_message

    def test_parse_returns_failed_result_on_struct_error(self):
        """struct.error in parse_func produces HandlerResult(success=False)."""
        def _bad_parse(archive, name_map):
            raise struct.error("unpack requires a buffer of 4 bytes")

        handler = AssetTypeHandler(
            class_names=["BadClass"],
            parse_func=_bad_parse,
            handler_name="BadHandler",
        )
        export = _make_export()
        archive = _make_archive()

        result = handler.parse(export, archive)

        assert result.success is False
        assert result.error_message is not None

    def test_parse_logs_warning_on_failure(self, caplog):
        """Handler failure should log at WARNING level."""
        def _bad_parse(archive, name_map):
            raise ValueError("parse error")

        handler = AssetTypeHandler(
            class_names=["BadClass"],
            parse_func=_bad_parse,
            handler_name="BadHandler",
        )
        export = _make_export()
        archive = _make_archive()

        with caplog.at_level(logging.WARNING, logger="uasset_read.parsers.asset_types"):
            result = handler.parse(export, archive)

        assert result.success is False
        assert any("BadHandler" in record.message for record in caplog.records)
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    def test_parse_success_returns_data(self):
        """Successful parse returns HandlerResult with data."""
        def _good_parse(archive, name_map):
            return {"parse_status": "success", "mesh_name": "Test"}

        handler = AssetTypeHandler(
            class_names=["GoodClass"],
            parse_func=_good_parse,
            handler_name="GoodHandler",
        )
        export = _make_export()
        archive = _make_archive()

        result = handler.parse(export, archive)

        assert result.success is True
        assert result.data["mesh_name"] == "Test"


# ---------------------------------------------------------------------------
# HandlerClassAdapter error propagation
# ---------------------------------------------------------------------------

class TestHandlerClassAdapterErrorVisibility:
    """HandlerClassAdapter.parse() must return HandlerResult(success=False) on failure."""

    def test_adapter_returns_failed_result_on_exception(self):
        """When underlying handler raises, HandlerResult(success=False) is returned."""
        adapter = HandlerClassAdapter(
            _MockHandlerForAdapter(), "FailingHandler"
        )
        export = _make_export()
        archive = _make_archive()

        result = adapter.parse(export, archive)

        assert result.success is False
        assert "adapter test failure" in result.error_message

    def test_adapter_returns_failed_result_on_struct_error(self):
        """struct.error in handler produces HandlerResult(success=False)."""
        adapter = HandlerClassAdapter(
            _MockHandlerForAdapterStructError(), "StructError"
        )
        export = _make_export()
        archive = _make_archive()

        result = adapter.parse(export, archive)

        assert result.success is False
        assert result.error_message is not None

    def test_adapter_logs_warning_on_failure(self, caplog):
        """Adapter should log at WARNING level on failure."""
        adapter = HandlerClassAdapter(
            _MockHandlerForAdapter(), "FailingHandler"
        )
        export = _make_export()
        archive = _make_archive()

        with caplog.at_level(logging.WARNING, logger="uasset_read.parsers.asset_types"):
            result = adapter.parse(export, archive)

        assert result.success is False
        assert any("FailingHandler" in record.message for record in caplog.records)
        assert any(record.levelno == logging.WARNING for record in caplog.records)


# ---------------------------------------------------------------------------
# _try_asset_type_handler error visibility (integration)
# ---------------------------------------------------------------------------

class TestTryAssetTypeHandlerErrorVisibility:
    """_try_asset_type_handler must make handler failures visible on the export."""

    def setup_method(self):
        """Register failing handler in a fresh registry."""
        reset_class_registry()
        self._registry = get_class_registry()
        self._registry.register(_FailingHandlerViaResult())

    def teardown_method(self):
        reset_class_registry()

    def test_failed_handler_sets_partial_parse_status(self):
        """When handler returns success=False, export.parse_status becomes 'partial'."""
        from uasset_read.parsers.property_parser import _try_asset_type_handler

        export = _make_export("FailingResultClass")
        archive = _make_archive()

        _try_asset_type_handler(export, archive, [], "FailingResultClass")

        # Use spec_set=False mock: check via __dict__ to avoid MagicMock auto-attr
        assert export.parse_status == "partial"

    def test_failed_handler_stores_error_message(self):
        """When handler returns success=False, export.handler_error is set."""
        from uasset_read.parsers.property_parser import _try_asset_type_handler

        export = _make_export("FailingResultClass")
        archive = _make_archive()

        _try_asset_type_handler(export, archive, [], "FailingResultClass")

        assert export.handler_error == "handler chose to report failure"

    def test_no_handler_does_not_modify_export(self):
        """When no handler is registered, export is unchanged."""
        from uasset_read.parsers.property_parser import _try_asset_type_handler

        # Use a real object with a known attribute to avoid MagicMock auto-attr
        class _FakeExport:
            pass

        export = _FakeExport()
        export.object_name = "TestExport"
        export.class_index = MagicMock()
        export.properties = []

        archive = _make_archive()

        _try_asset_type_handler(export, archive, [], "UnknownClass")

        # The function should return early (no handler found),
        # so no parse_status or handler_error should be set.
        assert not hasattr(export, "parse_status")
        assert not hasattr(export, "handler_error")

    def test_successful_handler_does_not_set_partial(self):
        """When handler succeeds, parse_status is NOT set to partial."""
        from uasset_read.parsers.property_parser import _try_asset_type_handler

        # Register a success handler
        self._registry.register(_SuccessHandler())

        export = _make_export("SuccessClass")
        archive = _make_archive()

        _try_asset_type_handler(export, archive, [], "SuccessClass")

        # Successful handler doesn't set parse_status to partial
        assert export.parse_status != "partial"


# ---------------------------------------------------------------------------
# _try_asset_type_handler with exception-raising handler (safety net)
# ---------------------------------------------------------------------------

class TestTryAssetTypeHandlerExceptionSafetyNet:
    """_try_asset_type_handler must handle unexpected exceptions gracefully."""

    def setup_method(self):
        reset_class_registry()
        self._registry = get_class_registry()
        self._registry.register(_FailingHandler())

    def teardown_method(self):
        reset_class_registry()

    def test_exception_handler_does_not_crash(self):
        """Handler that raises (instead of returning failed result) should not crash."""
        from uasset_read.parsers.property_parser import _try_asset_type_handler

        export = _make_export("FailingClass")
        archive = _make_archive()

        # Should not raise -- the safety net catch handles it
        _try_asset_type_handler(export, archive, [], "FailingClass")

    def test_exception_handler_logs_warning(self, caplog):
        """Handler that raises should log at WARNING level."""
        from uasset_read.parsers.property_parser import _try_asset_type_handler

        export = _make_export("FailingClass")
        archive = _make_archive()

        with caplog.at_level(logging.WARNING, logger="uasset_read.parsers.property_parser"):
            _try_asset_type_handler(export, archive, [], "FailingClass")

        assert any("AssetTypeHandler" in record.message for record in caplog.records)
        assert any(record.levelno == logging.WARNING for record in caplog.records)


# ---------------------------------------------------------------------------
# Registry integration test
# ---------------------------------------------------------------------------

class TestRegistryErrorVisibility:
    """Handler errors are visible through the registry's handler.parse() call."""

    def setup_method(self):
        reset_class_registry()
        self._registry = get_class_registry()
        self._registry.register(_FailingHandlerViaResult())

    def teardown_method(self):
        reset_class_registry()

    def test_registry_find_handler_returns_handler(self):
        """Registry finds the registered handler."""
        handler = self._registry.find_handler("FailingResultClass")
        assert handler is not None
        assert handler.handler_name == "FailingResultHandler"

    def test_registry_handler_returns_error_result(self):
        """Handler found via registry returns HandlerResult with error."""
        handler = self._registry.find_handler("FailingResultClass")
        export = _make_export()
        archive = _make_archive()

        result = handler.parse(export, archive)

        assert result.success is False
        assert result.error_message is not None
        assert len(result.error_message) > 0

    def test_registry_cache_invalidation(self):
        """After clear_cache, handler lookup still works."""
        self._registry.find_handler("FailingResultClass")  # populates cache
        self._registry.reset_cache()
        handler = self._registry.find_handler("FailingResultClass")
        assert handler is not None
        assert handler.handler_name == "FailingResultHandler"
