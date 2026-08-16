"""Tests for binary handler F-prefix normalization."""
from __future__ import annotations

from uasset_read.parsers.binary_or_native_handlers import BINARY_OR_NATIVE_HANDLERS


class TestHandlerPrefixNormalization:
    """Verify that non-F-prefixed struct types find their handlers."""

    def test_material_input_found(self):
        """MaterialInput (without F prefix) should find the handler."""
        handler = BINARY_OR_NATIVE_HANDLERS.get("MaterialInput")
        if handler is None:
            handler = BINARY_OR_NATIVE_HANDLERS.get("FMaterialInput")
        assert handler is not None, "No handler found for MaterialInput or FMaterialInput"

    def test_color_material_input_found(self):
        handler = BINARY_OR_NATIVE_HANDLERS.get("ColorMaterialInput")
        if handler is None:
            handler = BINARY_OR_NATIVE_HANDLERS.get("FColorMaterialInput")
        assert handler is not None

    def test_scalar_material_input_found(self):
        handler = BINARY_OR_NATIVE_HANDLERS.get("ScalarMaterialInput")
        if handler is None:
            handler = BINARY_OR_NATIVE_HANDLERS.get("FScalarMaterialInput")
        assert handler is not None

    def test_expression_output_found(self):
        """ExpressionOutput should find the ExpressionOutput handler."""
        handler = BINARY_OR_NATIVE_HANDLERS.get("ExpressionOutput")
        if handler is None:
            handler = BINARY_OR_NATIVE_HANDLERS.get("FExpressionOutput")
        assert handler is not None
